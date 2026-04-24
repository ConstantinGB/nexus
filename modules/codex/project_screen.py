from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path

from textual.widgets import Label, Button, Log
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.ui.base_project_screen import BaseProjectScreen, InputModal, _screen_css

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


def _first_heading(path: Path) -> str:
    try:
        for line in path.read_text(errors="replace").splitlines():
            stripped = line.lstrip("#").strip()
            if stripped:
                return stripped
    except Exception:
        pass
    return path.stem


class CodexProjectScreen(BaseProjectScreen):
    MODULE_KEY   = "codex"
    MODULE_LABEL = "CODEX"
    SETUP_FIELDS = [
        {"id": "vault_dir", "label": "Notes / vault directory",
         "placeholder": "~/codex"},
    ]

    DEFAULT_CSS = _screen_css("CodexProjectScreen")

    # ── Action buttons ────────────────────────────────────────────────────────

    def _compose_action_buttons(self) -> list:
        return [
            Button("New Note",   id="btn-new-note",  variant="primary"),
            Button("Search",     id="btn-search"),
            Button("Open Vault", id="btn-open-vault"),
            Button("Refresh",    id="btn-refresh"),
        ]

    # ── Main content ──────────────────────────────────────────────────────────

    async def _populate_content(self) -> None:
        area = self.query_one("#content-area", Vertical)
        await area.remove_children()

        vault_dir = Path(self._mod.get("vault_dir", "")).expanduser()
        widgets: list = [
            Horizontal(
                Label("Vault:", classes="info-key"),
                Label(str(vault_dir), classes="info-val"),
                classes="info-row",
            ),
        ]

        if vault_dir.exists():
            notes = sorted(vault_dir.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            widgets.append(
                Horizontal(
                    Label("Notes:", classes="info-key"),
                    Label(str(len(notes)), classes="info-val"),
                    classes="info-row",
                )
            )
            widgets.append(Label("Recent entries:", classes="section-label"))
            for note in notes[:20]:
                heading = _first_heading(note)
                widgets.append(Label(f"  {heading}", classes="hint"))
        else:
            widgets.append(Label(f"Vault not found: {vault_dir}", classes="status-err"))
            widgets.append(Label("Create the directory or check the path in setup.", classes="hint"))

        await area.mount(*widgets)

    # ── Button handler ────────────────────────────────────────────────────────

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
                lambda q: self.run_worker(self._run_cmd(
                    ["rg", "-n", "--color", "never", q, str(vault_dir)]
                )) if q else None,
            )
        elif bid == "btn-open-vault":
            self.run_worker(self._run_cmd(["xdg-open", str(vault_dir)]))
        elif bid == "btn-refresh":
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
            self.app.notify(f"Created: {dest.name}")
            self.run_worker(self._populate_content())
        except Exception:
            log.exception("Failed to create note: %s", dest)
            self.app.notify("Could not create note — see log.", severity="error")
