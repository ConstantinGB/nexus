from __future__ import annotations
from datetime import date, timedelta

from textual.widgets import Button, Label, Log
from textual.css.query import NoMatches

from nexus.ui.tui.base_project_screen import BaseProjectScreen, InputModal


def _get_calendar(project):
    from nexus.core.config_manager import get_module_mode, load_project_config
    from nexus.core.data.calendar import get_global_calendar, get_project_calendar
    mode = get_module_mode(load_project_config(project.slug), "calendar")
    return get_global_calendar() if mode == "integrated" else get_project_calendar(project.slug)


class ProjectScreen(BaseProjectScreen):
    MODULE_KEY   = "calendar"
    MODULE_LABEL = "Calendar"
    SETUP_FIELDS = []

    def _compose_action_buttons(self):
        yield Button("+ Add Event",  id="btn-add-event")
        yield Button("Delete Event", id="btn-del-event")
        yield Button("Refresh",      id="btn-refresh")

    def _handle_action(self, bid: str | None) -> None:
        if bid == "btn-add-event":
            self.app.push_screen(
                InputModal(
                    "Add Event",
                    "Format:  YYYY-MM-DD HH:MM Title\ne.g.  2026-05-10 09:00 Team sync",
                    f"{date.today().isoformat()} 09:00 ",
                ),
                self._on_add_event,
            )
        elif bid == "btn-del-event":
            self.app.push_screen(
                InputModal("Delete Event", "Event ID to delete (first 8 chars shown in list):", ""),
                self._on_del_event,
            )
        elif bid == "btn-refresh":
            self.run_worker(self._safe_populate())

    def _on_add_event(self, text: str | None) -> None:
        if not text:
            return
        parts = text.strip().split(" ", 2)
        if len(parts) < 2:
            self.app.notify("Format: YYYY-MM-DD HH:MM title", severity="error")
            return
        date_str = parts[0]
        time_str = parts[1]
        title    = parts[2] if len(parts) > 2 else "Event"
        try:
            cal = _get_calendar(self.project)
            cal.add_event(title=title, start=f"{date_str}T{time_str}:00")
            self.app.notify(f"Event added: {title}", severity="information")
            self.run_worker(self._safe_populate())
        except Exception as exc:
            self.app.notify(str(exc), severity="error")

    def _on_del_event(self, event_id: str | None) -> None:
        if not event_id:
            return
        try:
            cal = _get_calendar(self.project)
            # allow partial ID match
            eid = event_id.strip()
            match = next((e["id"] for e in cal.events if e["id"].startswith(eid)), eid)
            cal.delete_event(match)
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
            from nexus.core.config_manager import get_module_mode, load_project_config
            mode = get_module_mode(load_project_config(self.project.slug), "calendar")
            cal  = _get_calendar(self.project)

            log_widget.clear()
            source = "Global calendar" if mode == "integrated" else f"Project calendar ({self.project.slug})"
            log_widget.write_line(f"[{source}]  upcoming 30 days")
            log_widget.write_line("")

            today  = date.today()
            events = cal.get_events_in_range(today, today + timedelta(days=29))
            if not events:
                log_widget.write_line("  No upcoming events.")
                return

            # Group by date for a clean calendar-style list
            by_date: dict[str, list] = {}
            for e in sorted(events, key=lambda x: x["start"]):
                d = e["start"][:10]
                by_date.setdefault(d, []).append(e)

            for d_str, day_events in by_date.items():
                log_widget.write_line(f"  ── {d_str} ──")
                for e in day_events:
                    t_str = e["start"][11:16] if len(e["start"]) > 10 else ""
                    rec   = " ↻" if e.get("recurrence") else ""
                    log_widget.write_line(
                        f"    [{e['id'][:8]}]  {t_str}  {e['title']}{rec}"
                    )
        except Exception as exc:
            try:
                log_widget.write_line(f"Error loading calendar: {exc}")
            except Exception:
                pass
