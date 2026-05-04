from __future__ import annotations
import asyncio
import re
from datetime import datetime
from pathlib import Path

from textual.widgets import Label, Button, Log, DirectoryTree
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.core.config_manager import load_project_config, save_project_config
from nexus.ui.tui.base_project_screen import BaseProjectScreen, InputModal, _screen_css
from nexus.ui.tui.text_editor_screen import TextEditorScreen

log = get("codex.project_screen")

_NOTE_TEMPLATE = """\
---
id: {note_id}
title: {title}
tags: []
links: []
---

# {title}

"""


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "note"


def _has_tag(path: Path, tag: str) -> bool:
    if not tag:
        return True
    try:
        for line in path.read_text(errors="replace").splitlines():
            if line.startswith("tags:") and tag in line:
                return True
    except Exception:
        pass
    return False


def _first_heading(path: Path) -> str:
    """Return first non-empty non-frontmatter line, stripping leading #s."""
    try:
        lines = path.read_text(errors="replace").splitlines()
        in_front = bool(lines) and lines[0].strip() == "---"
        for i, line in enumerate(lines):
            if i == 0 and in_front:
                continue
            if in_front and line.strip() == "---":
                in_front = False
                continue
            if in_front:
                continue
            stripped = line.lstrip("#").strip()
            if stripped:
                return stripped
    except Exception:
        pass
    return path.stem


class ProjectScreen(BaseProjectScreen):
    MODULE_KEY        = "codex"
    MODULE_LABEL      = "CODEX"
    REQUIRED_BINARIES = [("rg", "ripgrep")]
    SETUP_FIELDS      = [
        {"id": "vault_dir", "label": "Notes / vault directory",
         "placeholder": "~/codex", "type": "dir"},
        {"id": "format",    "label": "Note format (markdown / latex)",
         "placeholder": "markdown"},
    ]

    DEFAULT_CSS = _screen_css("CodexProjectScreen") + """
    CodexProjectScreen .note-item {
        width: 1fr; height: 1; border: none; background: #0E0620;
        border-left: blank;
        color: $theme-text-dim; text-align: left; padding-left: 2; margin: 0;
    }
    CodexProjectScreen .note-item:hover {
        background: #1B0D3E; color: $theme-text; border-left: solid $theme-border;
    }
    CodexProjectScreen .note-item:focus {
        background: #241540; color: $theme-text; border-left: solid $theme-accent2;
    }
    CodexProjectScreen .note-group-label {
        color: $theme-accent2; height: 1; margin-top: 1; padding-left: 1;
    }

    CodexProjectScreen .expl-layout { height: 1fr; }
    CodexProjectScreen .expl-sidebar {
        width: 35; height: 1fr; border-right: solid $theme-border-dim;
    }
    CodexProjectScreen .expl-notes {
        width: 1fr; height: 1fr; overflow-y: auto;
    }
    #vault-tree { height: 1fr; background: #0E0620; }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._tag_filter: str = ""
        self._notes: list[Path] = []

    # ── Config helpers ────────────────────────────────────────────────────────

    def _on_before_save(self, data: dict) -> dict:
        vault_dir = Path(data.get("vault_dir", "")).expanduser()
        if vault_dir and not vault_dir.exists():
            vault_dir.mkdir(parents=True, exist_ok=True)
            self.app.notify(f"Created: {vault_dir}", severity="information")
        return {}

    def _connected_dirs(self) -> list[Path]:
        result = []
        for raw in self._mod.get("connected_dirs", []):
            p = Path(raw).expanduser()
            if p.exists():
                result.append(p)
        return result

    def _save_connected_dirs(self, dirs: list[Path]) -> None:
        self._mod["connected_dirs"] = [str(d) for d in dirs]
        self._cfg[self.MODULE_KEY] = self._mod
        save_project_config(self.project.slug, self._cfg)

    # ── Action buttons ────────────────────────────────────────────────────────

    def _compose_action_buttons(self) -> list:
        return [
            Button("New Note", id="btn-new-note", variant="primary"),
            Button("Search",   id="btn-search"),
            Button("Filter",   id="btn-filter-tags"),
            Button("↻",        id="btn-refresh"),
        ]

    # ── Main content ──────────────────────────────────────────────────────────

    async def _populate_content(self) -> None:
        area = self.query_one("#content-area", Vertical)
        await area.remove_children()

        vault_dir = Path(self._mod.get("vault_dir", "")).expanduser()
        connected = self._connected_dirs()

        info_widgets: list = [
            Horizontal(
                Label("Vault:", classes="info-key"),
                Label(str(vault_dir), classes="info-val"),
                classes="info-row",
            ),
        ]

        if not vault_dir.exists():
            info_widgets += [
                Label(f"Vault not found: {vault_dir}", classes="status-err"),
                Label("Create the directory or check the path in setup.", classes="hint"),
            ]
            await area.mount(*info_widgets)
            return

        # Gather notes
        all_notes_raw = await asyncio.to_thread(
            lambda: sorted(vault_dir.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        )
        if connected:
            seen = {n.resolve() for n in all_notes_raw}
            for cdir in connected:
                try:
                    extras = await asyncio.to_thread(
                        lambda d=cdir: sorted(d.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
                    )
                    for n in extras:
                        if n.resolve() not in seen:
                            seen.add(n.resolve())
                            all_notes_raw.append(n)
                except Exception:
                    pass
            all_notes_raw.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        notes = await asyncio.to_thread(
            lambda: [n for n in all_notes_raw if _has_tag(n, self._tag_filter)]
        ) if self._tag_filter else all_notes_raw

        filter_label = f"  (filtered: #{self._tag_filter})" if self._tag_filter else ""
        info_widgets.append(Horizontal(
            Label("Notes:", classes="info-key"),
            Label(f"{len(notes)}/{len(all_notes_raw)}{filter_label}", classes="info-val"),
            classes="info-row",
        ))
        if connected:
            info_widgets.append(Horizontal(
                Label("Sources:", classes="info-key"),
                Label(f"vault + {len(connected)} connected", classes="info-val"),
                classes="info-row",
            ))

        # Group notes by source: vault first, then each connected dir, alphabetical within each
        def _source_key(n: Path) -> tuple[int, str]:
            try:
                n.relative_to(vault_dir)
                return (0, "")
            except ValueError:
                pass
            for idx, cd in enumerate(connected):
                try:
                    n.relative_to(cd)
                    return (idx + 1, cd.name)
                except ValueError:
                    pass
            return (99, "")

        all_notes = notes[:]
        all_notes.sort(key=lambda n: (_source_key(n)[0],
                                      _first_heading(n).lower()))
        self._notes = all_notes[:20]

        # Build heading cache
        headings = {}
        for note in self._notes:
            headings[note] = await asyncio.to_thread(_first_heading, note)

        note_widgets: list = []
        last_source: str | None = None
        for i, note in enumerate(self._notes):
            src_idx, src_name = _source_key(note)
            group = "Vault" if src_idx == 0 else src_name
            if group != last_source:
                last_source = group
                note_widgets.append(Label(f"── {group} ──", classes="note-group-label"))
            heading = headings[note]
            note_widgets.append(
                Button(f"  {heading}", id=f"note-{i}", classes="note-item")
            )

        layout = Horizontal(
            Vertical(DirectoryTree(str(vault_dir), id="vault-tree"), classes="expl-sidebar"),
            Vertical(*note_widgets, classes="expl-notes"),
            classes="expl-layout",
        )
        await area.mount(*info_widgets, layout)

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self._open_note(event.path)

    def _primary_folder(self) -> Path | None:
        p = Path(self._mod.get("vault_dir", "")).expanduser()
        return p if str(p) != "." else None

    # ── Action handler ────────────────────────────────────────────────────────

    def _handle_action(self, bid: str | None) -> None:
        vault_dir = Path(self._mod.get("vault_dir", "")).expanduser()

        if bid == "btn-new-note":
            self.app.push_screen(
                InputModal("New Note", "Note title:", "My concept"),
                lambda title: self._create_note(title, vault_dir),
            )
        elif bid == "btn-search":
            self.app.push_screen(
                InputModal("Search", "Search query:", "keyword"),
                lambda q: self._do_search(q, vault_dir),
            )
        elif bid == "btn-filter-tags":
            self.app.push_screen(
                InputModal("Filter", "Tag name (blank to clear):", ""),
                self._apply_tag_filter,
            )
        elif bid == "btn-refresh":
            self.run_worker(self._populate_content())
        elif bid and bid.startswith("note-"):
            try:
                idx = int(bid.split("-", 1)[1])
            except ValueError:
                return
            if 0 <= idx < len(self._notes):
                self._open_note(self._notes[idx])

    def _do_search(self, q: str | None, vault_dir: Path) -> None:
        if not q:
            return
        import shutil
        if not shutil.which("rg"):
            self.app.notify("ripgrep (rg) is not installed.", severity="warning")
            return
        self.run_worker(self._run_cmd(["rg", "-C", "2", "--color", "never", q, str(vault_dir)]))

    def _apply_tag_filter(self, tag: str | None) -> None:
        self._tag_filter = (tag or "").strip()
        self.run_worker(self._populate_content())

    def _open_note(self, note_path: Path) -> None:
        try:
            content = note_path.read_text(errors="replace")
        except Exception:
            log.exception("Failed to read note: %s", note_path)
            self.app.notify("Could not read note — see log.", severity="error")
            return
        fmt  = self._mod.get("format", "markdown")
        lang = "markdown" if fmt == "markdown" else "text"
        self.app.push_screen(
            TextEditorScreen(content, language=lang, title=note_path.name),
            lambda saved, p=note_path: self._save_note(p, saved),
        )

    def _save_note(self, note_path: Path, content: str | None) -> None:
        if content is None:
            return
        try:
            note_path.write_text(content)
            self.app.notify(f"Saved: {note_path.name}", severity="information")
        except Exception:
            log.exception("Failed to save note: %s", note_path)
            self.app.notify("Could not save note — see log.", severity="error")
        self.run_worker(self._populate_content())

    def _create_note(self, title: str | None, vault_dir: Path) -> None:
        if not title:
            return
        slug = _slugify(title)
        dest = vault_dir / f"{slug}.md"
        note_id = datetime.now().strftime("%Y%m%d%H%M")
        try:
            vault_dir.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                dest.write_text(_NOTE_TEMPLATE.format(note_id=note_id, title=title))
        except Exception:
            log.exception("Failed to create note: %s", dest)
            self.app.notify("Could not create note — see log.", severity="error")
            return
        self._open_note(dest)
