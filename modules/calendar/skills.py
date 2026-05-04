from __future__ import annotations
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from nexus.ai.skill_registry import registry

_PROJECTS_ROOT = Path(__file__).parent.parent.parent / "projects"


def _data_dir(slug: str) -> Path:
    return _PROJECTS_ROOT / slug / "data" / "calendar"


async def _calendar_add(args: dict) -> str:
    from nexus.core.data.calendar import CalendarData
    slug = args["project_slug"]
    cal = CalendarData(_data_dir(slug))

    date_str = args["date"]
    time_str = args.get("time", "00:00")
    start = f"{date_str}T{time_str}:00"

    end = None
    duration = args.get("duration_minutes")
    if duration:
        start_dt = datetime.fromisoformat(start)
        end = (start_dt + timedelta(minutes=int(duration))).isoformat()

    event = cal.add_event(
        title=args["title"],
        start=start,
        end=end,
        description=args.get("description", ""),
    )
    return json.dumps({"ok": True, "event_id": event["id"], "start": event["start"]})


async def _calendar_list(args: dict) -> str:
    from nexus.core.data.calendar import CalendarData
    slug = args["project_slug"]
    cal = CalendarData(_data_dir(slug))

    target = args.get("date")
    days = int(args.get("days", 1))

    if target == "today" or target is None:
        start_d = date.today()
    else:
        start_d = date.fromisoformat(target)

    end_d = start_d + timedelta(days=days - 1)
    events = cal.get_events_in_range(start_d, end_d)

    if not events:
        return json.dumps({"events": [], "message": f"No events from {start_d} to {end_d}."})
    return json.dumps({"events": events})


async def _calendar_delete(args: dict) -> str:
    from nexus.core.data.calendar import CalendarData
    slug = args["project_slug"]
    cal = CalendarData(_data_dir(slug))
    cal.delete_event(args["event_id"])
    return json.dumps({"ok": True})


registry.register(
    scope="calendar",
    name="calendar_add",
    description="Add a calendar event.",
    schema={
        "type": "object",
        "properties": {
            "project_slug":     {"type": "string"},
            "title":            {"type": "string"},
            "date":             {"type": "string", "description": "ISO date YYYY-MM-DD"},
            "time":             {"type": "string", "description": "HH:MM (24h), default 00:00"},
            "description":      {"type": "string"},
            "duration_minutes": {"type": "integer"},
        },
        "required": ["project_slug", "title", "date"],
    },
    handler=_calendar_add,
)

registry.register(
    scope="calendar",
    name="calendar_list",
    description="List calendar events for a date or date range.",
    schema={
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "date":         {"type": "string", "description": "ISO date or 'today'"},
            "days":         {"type": "integer", "description": "Number of days to span (default 1)"},
        },
        "required": ["project_slug"],
    },
    handler=_calendar_list,
)

registry.register(
    scope="calendar",
    name="calendar_delete",
    description="Delete a calendar event by its ID.",
    schema={
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "event_id":     {"type": "string"},
        },
        "required": ["project_slug", "event_id"],
    },
    handler=_calendar_delete,
)
