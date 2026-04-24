from __future__ import annotations
import re
from pathlib import Path

from textual.app import ComposeResult
from textual.widgets import Label, Button, Log
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.core.project_manager import ProjectInfo
from nexus.ui.base_project_screen import BaseProjectScreen, InputModal, _screen_css

log = get("research.project_screen")


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "note"


def _first_line(path: Path) -> str:
    try:
        return path.read_text(errors="replace").splitlines()[0].lstrip("#").strip()
    except Exception:
        return ""


class ResearchProjectScreen(BaseProjectScreen):
    MODULE_KEY   = "research"
    MODULE_LABEL = "RESEARCH"
    SETUP_FIELDS = [
        {"id": "topic",     "label": "Research topic",
         "placeholder": "e.g. Machine learning interpretability"},
        {"id": "notes_dir", "label": "Notes directory",
         "placeholder": "~/research/notes"},
    ]

    DEFAULT_CSS = _screen_css("ResearchProjectScreen")

    # ── Action buttons ────────────────────────────────────────────────────────

    def _compose_action_buttons(self) -> list:
        return [
            Button("New Note",    id="btn-new-note",    variant="primary"),
            Button("Search",      id="btn-search"),
            Button("Export URLs", id="btn-export-urls"),
            Button("Refresh",     id="btn-refresh"),
        ]

    # ── Main content ──────────────────────────────────────────────────────────

    async def _populate_content(self) -> None:
        area = self.query_one("#content-area", Vertical)
        await area.remove_children()

        topic     = self._mod.get("topic", "")
        notes_dir = Path(self._mod.get("notes_dir", "")).expanduser()

        widgets: list = [
            Horizontal(
                Label("Topic:", classes="info-key"),
                Label(topic,    classes="info-val"),
                classes="info-row",
            ),
        ]

        if notes_dir.exists():
            notes = sorted(notes_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            widgets.append(
                Horizontal(
                    Label("Notes:", classes="info-key"),
                    Label(str(len(notes)), classes="info-val"),
                    classes="info-row",
                )
            )
            widgets.append(Label("Recent notes:", classes="section-label"))
            for note in notes[:20]:
                first = _first_line(note)
                display = f"  {note.name}" + (f" — {first}" if first else "")
                widgets.append(Label(display, classes="hint"))
        else:
            widgets.append(Label(f"Notes directory not found: {notes_dir}", classes="status-err"))
            widgets.append(Label("Create the directory and add .md files to get started.", classes="hint"))

        await area.mount(*widgets)

    # ── Button handler ────────────────────────────────────────────────────────

    def _handle_action(self, bid: str | None) -> None:
        notes_dir = Path(self._mod.get("notes_dir", "")).expanduser()

        if bid == "btn-new-note":
            self.app.push_screen(
                InputModal("New Note", "Note title or filename:", "my-note"),
                lambda title: self._create_note(title, notes_dir),
            )
        elif bid == "btn-search":
            self.app.push_screen(
                InputModal("Search", "Search query:", "keyword"),
                lambda q: self.run_worker(self._run_cmd(["rg", "-n", q, str(notes_dir)])) if q else None,
            )
        elif bid == "btn-export-urls":
            self.run_worker(self._run_cmd(["grep", "-rh", "http", str(notes_dir)]))
        elif bid == "btn-refresh":
            self.run_worker(self._populate_content())

    def _create_note(self, title: str | None, notes_dir: Path) -> None:
        if not title:
            return
        slug = _slugify(title)
        dest = notes_dir / f"{slug}.md"
        try:
            notes_dir.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                dest.write_text(f"# {title}\n\n")
            self.app.notify(f"Created: {dest.name}")
            self.run_worker(self._populate_content())
        except Exception:
            log.exception("Failed to create note: %s", dest)
            self.app.notify("Could not create note — see log.", severity="error")
