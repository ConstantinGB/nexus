from __future__ import annotations
import json
from datetime import date
from pathlib import Path

from textual.widgets import Button, Log

from nexus.ui.tui.base_project_screen import BaseProjectScreen, InputModal, _screen_css

_PROJECTS_ROOT = Path(__file__).parent.parent.parent / "projects"


def _data_dir(slug: str, sub: str) -> Path:
    return _PROJECTS_ROOT / slug / "data" / sub


class ProjectScreen(BaseProjectScreen):
    MODULE_KEY   = "operator"
    MODULE_LABEL = "Operator"
    SETUP_FIELDS = []   # data lives in projects/<slug>/data/ — no config needed

    DEFAULT_CSS = _screen_css("ProjectScreen")

    # ── Actions ───────────────────────────────────────────────────────────────

    def _compose_action_buttons(self) -> list[Button]:
        return [
            Button("Today's Brief",  id="act-brief",    variant="primary"),
            Button("New Note",       id="act-note",     variant="default"),
            Button("New Event",      id="act-event",    variant="default"),
            Button("New Task",       id="act-task",     variant="default"),
        ]

    def _handle_action(self, bid: str) -> None:
        if bid == "act-brief":
            self._trigger_brief()
        elif bid == "act-note":
            self.app.push_screen(
                InputModal("New Note", "Note title:", placeholder="Meeting notes, idea…"),
                self._on_note_title,
            )
        elif bid == "act-event":
            self.app.push_screen(
                InputModal("New Event", "Event (title YYYY-MM-DD HH:MM):", placeholder="Team sync 2026-05-05 14:00"),
                self._on_event_input,
            )
        elif bid == "act-task":
            self.app.push_screen(
                InputModal("New Task", "Task title:", placeholder="Buy groceries"),
                self._on_task_title,
            )

    # ── Content ───────────────────────────────────────────────────────────────

    async def _populate_content(self) -> None:
        try:
            log = self.query_one("#output-log", Log)
        except Exception:
            return

        slug = self.project.slug
        today = date.today()
        lines: list[str] = [f"Operator — {today.strftime('%A, %d %B %Y')}", ""]

        # Calendar
        try:
            from modules.operator.calendar_module import CalendarData
            cal = CalendarData(_data_dir(slug, "calendar"))
            events = cal.get_events_for_date(today)
            if events:
                lines.append(f"Today ({len(events)} event(s)):")
                for e in events:
                    t = e["start"][11:16] if len(e["start"]) > 10 else ""
                    lines.append(f"  {t}  {e['title']}")
            else:
                lines.append("Today: no events scheduled.")
        except Exception as exc:
            lines.append(f"[calendar error: {exc}]")

        lines.append("")

        # Pending tasks
        try:
            from modules.operator.todo_module import TodoData
            todo = TodoData(_data_dir(slug, "todo"))
            pending = todo.get_pending()
            if pending:
                lines.append(f"Pending tasks ({len(pending)}):")
                for t in pending[:5]:
                    priority = {"high": "!", "medium": "·", "low": " "}.get(t.get("priority", "medium"), "·")
                    lines.append(f"  [{priority}] {t['title']}")
                if len(pending) > 5:
                    lines.append(f"  … and {len(pending) - 5} more")
            else:
                lines.append("No pending tasks.")
        except Exception as exc:
            lines.append(f"[todo error: {exc}]")

        lines.append("")

        # Notes count
        try:
            from modules.operator.notes_module import NotesData
            notes = NotesData(_data_dir(slug, "notes"))
            lines.append(f"Notes: {len(notes.notes)} stored.")
        except Exception as exc:
            lines.append(f"[notes error: {exc}]")

        lines.append("")
        lines.append("Open the Chat panel to interact with the operator via AI.")

        try:
            log.clear()
            for line in lines:
                log.write_line(line)
        except Exception:
            pass

    # ── Skill scope for chat panel ────────────────────────────────────────────

    @property
    def skill_scopes(self) -> list[str]:
        return ["global", "operator"]

    # ── Action callbacks ──────────────────────────────────────────────────────

    def _trigger_brief(self) -> None:
        from nexus.ui.tui.chat_panel import ChatPanel
        try:
            panel = self.query_one(ChatPanel)
            if not panel.display:
                self._set_panel_mode("chat")
        except Exception:
            self._set_panel_mode("chat")
        slug = self.project.slug
        today = date.today().isoformat()
        prompt = (
            f"Good morning! Please give me a brief for today ({today}). "
            f"Check my calendar for today's events (project_slug='{slug}'), "
            f"list my pending tasks, and mention any recent notes if relevant."
        )
        self.call_after_refresh(self._send_brief, prompt)

    async def _send_brief(self, prompt: str) -> None:
        from nexus.ui.tui.chat_panel import ChatPanel
        try:
            panel = self.query_one(ChatPanel)
            panel._submit_message(prompt)
        except Exception:
            pass

    def _on_note_title(self, title: str | None) -> None:
        if not title:
            return
        try:
            from modules.operator.notes_module import NotesData
            notes = NotesData(_data_dir(self.project.slug, "notes"))
            notes.create_note(title)
            self.notify(f"Note created: {title}")
            self.run_worker(self._populate_content())
        except Exception as exc:
            self.notify(f"Failed to create note: {exc}", severity="error")

    def _on_event_input(self, raw: str | None) -> None:
        if not raw:
            return
        parts = raw.strip().split()
        # Expect: "title words... YYYY-MM-DD HH:MM" or just "title words... YYYY-MM-DD"
        event_date = None
        event_time = "00:00"
        title_parts = []
        for part in parts:
            if len(part) == 10 and part.count("-") == 2:
                event_date = part
            elif len(part) == 5 and ":" in part:
                event_time = part
            else:
                title_parts.append(part)

        if not event_date:
            self.notify("Include a date (YYYY-MM-DD) in the event description.", severity="warning")
            return
        title = " ".join(title_parts) or "Event"
        try:
            from modules.operator.calendar_module import CalendarData
            cal = CalendarData(_data_dir(self.project.slug, "calendar"))
            cal.add_event(title=title, start=f"{event_date}T{event_time}:00")
            self.notify(f"Event added: {title} on {event_date}")
            self.run_worker(self._populate_content())
        except Exception as exc:
            self.notify(f"Failed to add event: {exc}", severity="error")

    def _on_task_title(self, title: str | None) -> None:
        if not title:
            return
        try:
            from modules.operator.todo_module import TodoData
            todo = TodoData(_data_dir(self.project.slug, "todo"))
            lst = todo.ensure_default_list()
            todo.add_task(lst["id"], title)
            self.notify(f"Task added: {title}")
            self.run_worker(self._populate_content())
        except Exception as exc:
            self.notify(f"Failed to add task: {exc}", severity="error")
