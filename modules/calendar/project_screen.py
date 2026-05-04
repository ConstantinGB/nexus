from __future__ import annotations
from datetime import date
from pathlib import Path

from textual.widgets import Button, Label, Log
from textual.css.query import NoMatches

from nexus.core.project_manager import ProjectInfo
from nexus.ui.tui.base_project_screen import BaseProjectScreen, InputModal

_PROJECTS_ROOT = Path(__file__).parent.parent.parent / "projects"


def _data_dir(slug: str) -> Path:
    return _PROJECTS_ROOT / slug / "data" / "calendar"


class ProjectScreen(BaseProjectScreen):
    MODULE_KEY   = "calendar"
    MODULE_LABEL = "Calendar"
    SETUP_FIELDS = []

    def _compose_action_buttons(self):
        yield Button("+ Add Event",    id="btn-add-event")
        yield Button("Delete Event",   id="btn-del-event")

    def _handle_action(self, bid: str | None) -> None:
        if bid == "btn-add-event":
            self.app.push_screen(
                InputModal(
                    "Add Event",
                    "Event title (YYYY-MM-DD HH:MM title — e.g. 2026-05-05 09:00 Team sync):",
                    "2026-05-05 09:00 Team sync",
                ),
                self._on_add_event,
            )
        elif bid == "btn-del-event":
            self.app.push_screen(
                InputModal("Delete Event", "Event ID to delete:", ""),
                self._on_del_event,
            )

    def _on_add_event(self, text: str | None) -> None:
        if not text:
            return
        parts = text.strip().split(" ", 2)
        if len(parts) < 2:
            self.app.notify("Format: YYYY-MM-DD HH:MM title", severity="error")
            return
        date_str = parts[0]
        time_str = parts[1] if len(parts) > 1 else "00:00"
        title = parts[2] if len(parts) > 2 else "Event"
        try:
            from nexus.core.data.calendar import CalendarData
            cal = CalendarData(_data_dir(self.project.slug))
            event = cal.add_event(
                title=title,
                start=f"{date_str}T{time_str}:00",
            )
            self.app.notify(f"Event added: {title}", severity="information")
            self.run_worker(self._safe_populate())
        except Exception as exc:
            self.app.notify(str(exc), severity="error")

    def _on_del_event(self, event_id: str | None) -> None:
        if not event_id:
            return
        try:
            from nexus.core.data.calendar import CalendarData
            cal = CalendarData(_data_dir(self.project.slug))
            cal.delete_event(event_id.strip())
            self.app.notify("Event deleted.", severity="information")
            self.run_worker(self._safe_populate())
        except Exception as exc:
            self.app.notify(str(exc), severity="error")

    async def _populate_content(self) -> None:
        try:
            log_widget = self.query_one("#output-log", Log)
        except NoMatches:
            return
        try:
            from nexus.core.data.calendar import CalendarData
            cal = CalendarData(_data_dir(self.project.slug))
            events = cal.get_upcoming(days=30)
            log_widget.clear()
            if not events:
                log_widget.write_line("No upcoming events in the next 30 days.")
            else:
                log_widget.write_line(f"Upcoming events (next 30 days): {len(events)}")
                for e in sorted(events, key=lambda x: x["start"]):
                    start = e["start"]
                    d_str = start[:10]
                    t_str = start[11:16] if len(start) > 10 else ""
                    log_widget.write_line(f"  [{e['id'][:8]}]  {d_str} {t_str}  {e['title']}")
        except Exception as exc:
            try:
                log_widget.write_line(f"Error loading calendar: {exc}")
            except Exception:
                pass
