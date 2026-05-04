from __future__ import annotations
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from nexus.ai.skill_registry import registry
from nexus.core.config_manager import load_project_config

_PROJECTS_ROOT = Path(__file__).parent.parent.parent / "projects"


def _data_dir(slug: str, sub: str) -> Path:
    return _PROJECTS_ROOT / slug / "data" / sub


# ── Calendar ──────────────────────────────────────────────────────────────────

async def _calendar_add(args: dict) -> str:
    from modules.operator.calendar_module import CalendarData
    slug = args["project_slug"]
    cal = CalendarData(_data_dir(slug, "calendar"))

    # Build ISO datetime string from date + optional time
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
    from modules.operator.calendar_module import CalendarData
    slug = args["project_slug"]
    cal = CalendarData(_data_dir(slug, "calendar"))

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
    from modules.operator.calendar_module import CalendarData
    slug = args["project_slug"]
    cal = CalendarData(_data_dir(slug, "calendar"))
    cal.delete_event(args["event_id"])
    return json.dumps({"ok": True})


registry.register(
    scope="operator",
    name="operator_calendar_add",
    description="Add a calendar event for the operator project.",
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
    scope="operator",
    name="operator_calendar_list",
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
    scope="operator",
    name="operator_calendar_delete",
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

# ── Notes ─────────────────────────────────────────────────────────────────────

async def _note_create(args: dict) -> str:
    from modules.operator.notes_module import NotesData
    slug = args["project_slug"]
    notes = NotesData(_data_dir(slug, "notes"))
    note = notes.create_note(
        title=args["title"],
        content=args.get("content", ""),
        tags=args.get("tags", []),
    )
    return json.dumps({"ok": True, "note_id": note["id"], "file": note["file"]})


async def _note_search(args: dict) -> str:
    from modules.operator.notes_module import NotesData
    slug = args["project_slug"]
    notes = NotesData(_data_dir(slug, "notes"))
    results = notes.search(args["query"])
    return json.dumps({"results": results})


async def _note_get(args: dict) -> str:
    from modules.operator.notes_module import NotesData
    slug = args["project_slug"]
    notes = NotesData(_data_dir(slug, "notes"))
    content = notes.get_content(args["note_id"])
    meta = notes.get_by_id(args["note_id"])
    return json.dumps({"meta": meta, "content": content})


async def _note_update(args: dict) -> str:
    from modules.operator.notes_module import NotesData
    slug = args["project_slug"]
    notes = NotesData(_data_dir(slug, "notes"))
    notes.update_note(args["note_id"], args["content"])
    return json.dumps({"ok": True})


async def _note_delete(args: dict) -> str:
    from modules.operator.notes_module import NotesData
    slug = args["project_slug"]
    notes = NotesData(_data_dir(slug, "notes"))
    notes.delete_note(args["note_id"])
    return json.dumps({"ok": True})


registry.register(
    scope="operator",
    name="operator_note_create",
    description="Create a new markdown note.",
    schema={
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "title":        {"type": "string"},
            "content":      {"type": "string"},
            "tags":         {"type": "array", "items": {"type": "string"}},
        },
        "required": ["project_slug", "title"],
    },
    handler=_note_create,
)

registry.register(
    scope="operator",
    name="operator_note_search",
    description="Search notes by title or tags.",
    schema={
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "query":        {"type": "string"},
        },
        "required": ["project_slug", "query"],
    },
    handler=_note_search,
)

registry.register(
    scope="operator",
    name="operator_note_get",
    description="Get a note's metadata and full content by ID.",
    schema={
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "note_id":      {"type": "string"},
        },
        "required": ["project_slug", "note_id"],
    },
    handler=_note_get,
)

registry.register(
    scope="operator",
    name="operator_note_update",
    description="Update the content of an existing note.",
    schema={
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "note_id":      {"type": "string"},
            "content":      {"type": "string"},
        },
        "required": ["project_slug", "note_id", "content"],
    },
    handler=_note_update,
)

registry.register(
    scope="operator",
    name="operator_note_delete",
    description="Delete a note by ID.",
    schema={
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "note_id":      {"type": "string"},
        },
        "required": ["project_slug", "note_id"],
    },
    handler=_note_delete,
)

# ── Todo ──────────────────────────────────────────────────────────────────────

async def _todo_add(args: dict) -> str:
    from modules.operator.todo_module import TodoData
    slug = args["project_slug"]
    todo = TodoData(_data_dir(slug, "todo"))
    lst = todo.ensure_default_list()

    list_name = args.get("list_name")
    if list_name:
        named = todo.get_list_by_name(list_name)
        if named is None:
            named = todo.add_list(list_name)
        lst = named

    task = todo.add_task(
        list_id=lst["id"],
        title=args["title"],
        priority=args.get("priority", "medium"),
        deadline=args.get("deadline"),
    )
    return json.dumps({"ok": True, "task_id": task["id"], "list": lst["name"]})


async def _todo_list(args: dict) -> str:
    from modules.operator.todo_module import TodoData
    slug = args["project_slug"]
    todo = TodoData(_data_dir(slug, "todo"))

    filter_mode = args.get("filter", "all")
    list_name = args.get("list_name")

    list_id = None
    if list_name:
        named = todo.get_list_by_name(list_name)
        if named:
            list_id = named["id"]

    if filter_mode == "pending":
        tasks = todo.get_pending(list_id)
        return json.dumps({"tasks": tasks})

    # Return all lists (or filtered list)
    lists_out = []
    for lst in todo.lists:
        if list_id and lst["id"] != list_id:
            continue
        lists_out.append({"list": lst["name"], "tasks": lst["tasks"]})
    return json.dumps({"lists": lists_out})


async def _todo_complete(args: dict) -> str:
    from modules.operator.todo_module import TodoData
    slug = args["project_slug"]
    todo = TodoData(_data_dir(slug, "todo"))
    task_id = args["task_id"]
    lst, task = todo.find_task(task_id)
    if task is None:
        return json.dumps({"error": f"Task {task_id!r} not found."})
    todo.complete_task(lst["id"], task_id)
    return json.dumps({"ok": True, "task": task["title"]})


async def _todo_delete(args: dict) -> str:
    from modules.operator.todo_module import TodoData
    slug = args["project_slug"]
    todo = TodoData(_data_dir(slug, "todo"))
    task_id = args["task_id"]
    lst, task = todo.find_task(task_id)
    if task is None:
        return json.dumps({"error": f"Task {task_id!r} not found."})
    todo.delete_task(lst["id"], task_id)
    return json.dumps({"ok": True})


registry.register(
    scope="operator",
    name="operator_todo_add",
    description="Add a task. Creates a default list if none exist.",
    schema={
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "title":        {"type": "string"},
            "list_name":    {"type": "string", "description": "List name (created if missing)"},
            "priority":     {"type": "string", "enum": ["low", "medium", "high"]},
            "deadline":     {"type": "string", "description": "ISO datetime YYYY-MM-DDTHH:MM"},
        },
        "required": ["project_slug", "title"],
    },
    handler=_todo_add,
)

registry.register(
    scope="operator",
    name="operator_todo_list",
    description="List tasks. filter='pending' returns only incomplete tasks.",
    schema={
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "list_name":    {"type": "string"},
            "filter":       {"type": "string", "enum": ["all", "pending"], "description": "Default: all"},
        },
        "required": ["project_slug"],
    },
    handler=_todo_list,
)

registry.register(
    scope="operator",
    name="operator_todo_complete",
    description="Mark a task as completed by its ID.",
    schema={
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "task_id":      {"type": "string"},
        },
        "required": ["project_slug", "task_id"],
    },
    handler=_todo_complete,
)

registry.register(
    scope="operator",
    name="operator_todo_delete",
    description="Delete a task and its subtasks by ID.",
    schema={
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "task_id":      {"type": "string"},
        },
        "required": ["project_slug", "task_id"],
    },
    handler=_todo_delete,
)
