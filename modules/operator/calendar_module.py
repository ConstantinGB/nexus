from __future__ import annotations
import json
from datetime import datetime, date, timedelta
from pathlib import Path


class CalendarData:
    """Calendar storage — ported from Thallid, PyQt6 removed."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.events_file = self.data_dir / "events.json"
        self.events: list[dict] = self._load()

    def _load(self) -> list[dict]:
        if self.events_file.exists():
            with open(self.events_file) as f:
                return json.load(f)
        return []

    def _save(self) -> None:
        with open(self.events_file, "w") as f:
            json.dump(self.events, f, indent=2)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def add_event(
        self,
        title: str,
        start: str,
        end: str | None = None,
        description: str = "",
        location: str = "",
        recurrence: dict | None = None,
    ) -> dict:
        event = {
            "id": datetime.now().isoformat(),
            "title": title,
            "start": start,
            "end": end or start,
            "description": description,
            "location": location,
            "recurrence": recurrence,
        }
        self.events.append(event)
        self._save()
        return event

    def update_event(self, event_id: str, **kwargs) -> dict | None:
        for event in self.events:
            if event["id"] == event_id:
                event.update(kwargs)
                self._save()
                return event
        return None

    def delete_event(self, event_id: str) -> None:
        self.events = [e for e in self.events if e["id"] != event_id]
        self._save()

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_events_for_date(self, d: date) -> list[dict]:
        date_str = d.isoformat()
        return [
            e for e in self.events
            if e["start"].startswith(date_str)
            or (e.get("recurrence") and self._occurs_on(e, d))
        ]

    def get_events_in_range(self, start: date, end: date) -> list[dict]:
        results = []
        current = start
        while current <= end:
            for e in self.get_events_for_date(current):
                if e not in results:
                    results.append(e)
            current += timedelta(days=1)
        return results

    def get_upcoming(self, days: int = 7) -> list[dict]:
        today = date.today()
        return self.get_events_in_range(today, today + timedelta(days=days - 1))

    def _occurs_on(self, event: dict, d: date) -> bool:
        rec = event.get("recurrence")
        if not rec:
            return False
        start_dt = datetime.fromisoformat(event["start"]).date()
        if d < start_dt:
            return False
        until = rec.get("until")
        if until and d > datetime.fromisoformat(until).date():
            return False
        interval = rec.get("interval", 1)
        rec_type = rec.get("type")
        if rec_type == "daily":
            return (d - start_dt).days % interval == 0
        if rec_type == "weekly":
            return d.weekday() == start_dt.weekday() and (d - start_dt).days // 7 % interval == 0
        if rec_type == "monthly":
            return d.day == start_dt.day and ((d.year - start_dt.year) * 12 + d.month - start_dt.month) % interval == 0
        if rec_type == "yearly":
            return d.month == start_dt.month and d.day == start_dt.day and (d.year - start_dt.year) % interval == 0
        return False
