from __future__ import annotations
from pathlib import Path

from textual.widgets import Button, Label, Log
from textual.css.query import NoMatches

from nexus.core.project_manager import ProjectInfo
from nexus.ui.tui.base_project_screen import BaseProjectScreen, InputModal

_PROJECTS_ROOT = Path(__file__).parent.parent.parent / "projects"


def _data_dir(slug: str) -> Path:
    return _PROJECTS_ROOT / slug / "data" / "notes"


class ProjectScreen(BaseProjectScreen):
    MODULE_KEY   = "notes"
    MODULE_LABEL = "Notes"
    SETUP_FIELDS = []

    def _compose_action_buttons(self):
        yield Button("+ New Note",    id="btn-new-note")
        yield Button("Delete Note",   id="btn-del-note")

    def _handle_action(self, bid: str | None) -> None:
        if bid == "btn-new-note":
            self.app.push_screen(
                InputModal("New Note", "Note title:", "My note"),
                self._on_new_note,
            )
        elif bid == "btn-del-note":
            self.app.push_screen(
                InputModal("Delete Note", "Note ID to delete:", ""),
                self._on_del_note,
            )

    def _on_new_note(self, title: str | None) -> None:
        if not title:
            return
        try:
            from nexus.core.data.notes import NotesData
            nd = NotesData(_data_dir(self.project.slug))
            note = nd.create_note(title.strip())
            self.app.notify(f"Note created: {title}", severity="information")
            self.run_worker(self._safe_populate())
        except Exception as exc:
            self.app.notify(str(exc), severity="error")

    def _on_del_note(self, note_id: str | None) -> None:
        if not note_id:
            return
        try:
            from nexus.core.data.notes import NotesData
            nd = NotesData(_data_dir(self.project.slug))
            nd.delete_note(note_id.strip())
            self.app.notify("Note deleted.", severity="information")
            self.run_worker(self._safe_populate())
        except Exception as exc:
            self.app.notify(str(exc), severity="error")

    async def _populate_content(self) -> None:
        try:
            log_widget = self.query_one("#output-log", Log)
        except NoMatches:
            return
        try:
            from nexus.core.data.notes import NotesData
            nd = NotesData(_data_dir(self.project.slug))
            log_widget.clear()
            if not nd.notes:
                log_widget.write_line("No notes yet. Use '+ New Note' to create your first note.")
            else:
                log_widget.write_line(f"Notes: {len(nd.notes)}")
                for n in nd.notes:
                    tags = ", ".join(n.get("tags", []))
                    tag_str = f"  [{tags}]" if tags else ""
                    log_widget.write_line(f"  [{n['id']}]  {n['title']}{tag_str}  (modified: {n.get('modified', '')[:10]})")
        except Exception as exc:
            try:
                log_widget.write_line(f"Error loading notes: {exc}")
            except Exception:
                pass
