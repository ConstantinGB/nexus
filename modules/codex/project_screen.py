from __future__ import annotations
import asyncio
import re
from datetime import datetime
from pathlib import Path

from textual.widgets import Label, Button, Log
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.core.config_manager import load_project_config, save_project_config
from nexus.ui.base_project_screen import BaseProjectScreen, InputModal, _screen_css
from nexus.ui.text_editor_screen import TextEditorScreen

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


class CodexProjectScreen(BaseProjectScreen):
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
        width: 1fr; height: 2; border: none; background: #1A1035;
        border-left: solid #3A2260;
        color: #8080AA; text-align: left; margin: 0 0 0 0;
    }
    CodexProjectScreen .note-item:hover {
        background: #2D1B4E; color: #E0E0FF; border-left: solid #00B4FF;
    }
    CodexProjectScreen .note-group-label {
        color: #00FF88; height: 1; margin-top: 1; padding-left: 1;
    }

    CodexProjectScreen .expl-layout {
        height: 1fr;
    }
    CodexProjectScreen .expl-sidebar {
        width: 36; height: 1fr; border-right: solid #3A2260;
        padding: 0 1; background: #130822; overflow-y: auto;
    }
    CodexProjectScreen .expl-section-hdr {
        color: #00FF88; height: 1; margin-top: 1; text-align: center; width: 1fr;
    }
    CodexProjectScreen .expl-notes {
        width: 1fr; height: 1fr; padding-left: 1; overflow-y: auto;
    }

    CodexProjectScreen .expl-row { height: 2; }
    CodexProjectScreen .expl-expand-btn {
        width: 3; height: 2; border: none; background: transparent;
        min-width: 3; padding: 0; color: #555588;
    }
    CodexProjectScreen .expl-expand-btn:hover { color: #00B4FF; }
    CodexProjectScreen .expl-folder-btn {
        width: 5; height: 2; border: solid #3A2260; background: transparent;
        color: #8080AA; min-width: 5; padding: 0;
    }
    CodexProjectScreen .expl-folder-btn:hover { color: #00FF88; border: solid #00FF88; }
    CodexProjectScreen .expl-folder-btn.-connected {
        color: #00FF88; border: solid #00FF88;
    }
    CodexProjectScreen .expl-name-lbl { color: #8080AA; width: 1fr; }
    CodexProjectScreen .expl-proj-lbl { color: #6060AA; width: 1fr; }

    CodexProjectScreen .expl-sub-row { height: 2; padding-left: 5; }
    CodexProjectScreen .expl-sub-btn {
        width: 5; height: 2; border: solid #241540; background: transparent;
        color: #555588; min-width: 5; padding: 0;
    }
    CodexProjectScreen .expl-sub-btn:hover { color: #8080AA; }
    CodexProjectScreen .expl-sub-btn.-connected {
        color: #00FF88; border: solid #00FF88;
    }
    CodexProjectScreen .expl-sub-lbl { color: #555588; width: 1fr; }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._tag_filter: str = ""
        self._notes: list[Path] = []
        self._dir_button_map: dict[str, Path] = {}
        self._expanded_dirs: set[Path] = set()

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
        self._dir_button_map.clear()

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

        # Explorer sidebar + notes — use classes (not IDs) to avoid DuplicateIds on refresh
        explorer_widgets = await self._build_explorer_panel(vault_dir, connected)
        layout = Horizontal(
            Vertical(*explorer_widgets, classes="expl-sidebar"),
            Vertical(*note_widgets,     classes="expl-notes"),
            classes="expl-layout",
        )
        await area.mount(*info_widgets, layout)

    async def _build_explorer_panel(self, vault_dir: Path, connected: list[Path]) -> list:
        widgets: list = [Label("── Vault ──", classes="expl-section-hdr")]
        try:
            subdirs = sorted([d for d in vault_dir.iterdir() if d.is_dir()], key=lambda d: d.name)
        except Exception:
            subdirs = []

        connected_set = {d.resolve() for d in connected}

        for j, subdir in enumerate(subdirs):
            btn_id = f"expl-vault-{j}"
            self._dir_button_map[btn_id] = subdir
            is_conn = subdir.resolve() in connected_set
            icon = "[+]" if is_conn else "[ ]"
            conn_class = "expl-folder-btn -connected" if is_conn else "expl-folder-btn"

            try:
                has_subdirs = any(d.is_dir() for d in subdir.iterdir())
            except Exception:
                has_subdirs = False

            is_expanded = subdir in self._expanded_dirs
            # expand button on the LEFT so it's immediately visible next to the name
            row_widgets = []
            if has_subdirs:
                exp_id = f"expl-expand-{j}"
                expand_icon = "v" if is_expanded else ">"
                row_widgets.append(Button(expand_icon, id=exp_id, classes="expl-expand-btn"))
            row_widgets += [
                Button(icon, id=btn_id, classes=conn_class),
                Label(subdir.name, classes="expl-name-lbl"),
            ]
            widgets.append(Horizontal(*row_widgets, classes="expl-row"))

            if has_subdirs and is_expanded:
                try:
                    child_dirs = sorted([d for d in subdir.iterdir() if d.is_dir()], key=lambda d: d.name)
                except Exception:
                    child_dirs = []
                for k, child in enumerate(child_dirs):
                    sub_id = f"expl-sub-{j}-{k}"
                    self._dir_button_map[sub_id] = child
                    is_sub_conn = child.resolve() in connected_set
                    sub_icon = "[+]" if is_sub_conn else "[ ]"
                    sub_cls = "expl-sub-btn -connected" if is_sub_conn else "expl-sub-btn"
                    widgets.append(Horizontal(
                        Button(sub_icon, id=sub_id, classes=sub_cls),
                        Label(child.name, classes="expl-sub-lbl"),
                        classes="expl-sub-row",
                    ))

        cross = self._get_cross_project_dirs(vault_dir)
        if cross:
            widgets.append(Label("── Projects ──", classes="expl-section-hdr"))
            from nexus.core.module_manager import MODULE_PREFIX
            for k, (mod_label, proj_name, dir_path) in enumerate(cross):
                chk_id = f"expl-proj-{k}"
                self._dir_button_map[chk_id] = dir_path
                is_conn = dir_path.resolve() in connected_set
                icon = "[+]" if is_conn else "[ ]"
                conn_class = "expl-folder-btn -connected" if is_conn else "expl-folder-btn"
                prefix = MODULE_PREFIX.get(mod_label, "")
                display = proj_name[len(prefix) + 1:] if prefix and proj_name.lower().startswith(prefix + "-") else proj_name
                widgets.append(Horizontal(
                    Button(icon, id=chk_id, classes=conn_class),
                    Label(f"{display} ({mod_label})", classes="expl-proj-lbl"),
                    classes="expl-row",
                ))

        widgets += [Label(""), Label("")]
        return widgets

    def _get_cross_project_dirs(self, vault_dir: Path) -> list[tuple[str, str, Path]]:
        from nexus.core.project_manager import list_projects
        dir_keys = {"research": "notes_dir", "codex": "vault_dir", "org": "output_dir", "journal": "journal_dir"}
        result = []
        for project in list_projects():
            if project.slug == self.project.slug:
                continue
            key = dir_keys.get(project.module)
            if key is None:
                continue
            cfg = load_project_config(project.slug)
            raw = cfg.get(project.module, {}).get(key, "")
            if not raw:
                continue
            p = Path(raw).expanduser()
            if p.exists() and p.resolve() != vault_dir.resolve():
                result.append((project.module, project.name, p))
        return result

    def _primary_folder(self) -> Path | None:
        p = Path(self._mod.get("vault_dir", "")).expanduser()
        return p if str(p) != "." else None

    # ── Action handler ────────────────────────────────────────────────────────

    def _handle_action(self, bid: str | None) -> None:
        vault_dir = Path(self._mod.get("vault_dir", "")).expanduser()

        if bid and bid.startswith("expl-expand-"):
            try:
                j = int(bid[len("expl-expand-"):])
            except ValueError:
                return
            try:
                subdirs = sorted([d for d in vault_dir.iterdir() if d.is_dir()], key=lambda d: d.name)
                subdir = subdirs[j]
            except (IndexError, Exception):
                return
            if subdir in self._expanded_dirs:
                self._expanded_dirs.discard(subdir)
            else:
                self._expanded_dirs.add(subdir)
            self.run_worker(self._populate_content())

        elif bid and bid.startswith("expl-"):
            path = self._dir_button_map.get(bid)
            if path is None:
                return
            connected = [Path(d).expanduser() for d in self._mod.get("connected_dirs", [])]
            resolved = {d.resolve() for d in connected}
            if path.resolve() in resolved:
                connected = [d for d in connected if d.resolve() != path.resolve()]
            else:
                connected.append(path)
            self._save_connected_dirs(connected)
            self.run_worker(self._populate_content())

        elif bid == "btn-new-note":
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
