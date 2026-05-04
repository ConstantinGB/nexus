from __future__ import annotations
import json
from pathlib import Path

from nexus.ai.skill_registry import registry

_PROJECTS_ROOT = Path(__file__).parent.parent.parent / "projects"


def _data_dir(slug: str) -> Path:
    return _PROJECTS_ROOT / slug / "data" / "todo"


async def _todo_add(args: dict) -> str:
    from nexus.core.data.tasks import TodoData
    slug = args["project_slug"]
    todo = TodoData(_data_dir(slug))
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
    from nexus.core.data.tasks import TodoData
    slug = args["project_slug"]
    todo = TodoData(_data_dir(slug))

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

    lists_out = []
    for lst in todo.lists:
        if list_id and lst["id"] != list_id:
            continue
        lists_out.append({"list": lst["name"], "tasks": lst["tasks"]})
    return json.dumps({"lists": lists_out})


async def _todo_complete(args: dict) -> str:
    from nexus.core.data.tasks import TodoData
    slug = args["project_slug"]
    todo = TodoData(_data_dir(slug))
    task_id = args["task_id"]
    lst, task = todo.find_task(task_id)
    if task is None:
        return json.dumps({"error": f"Task {task_id!r} not found."})
    todo.complete_task(lst["id"], task_id)
    return json.dumps({"ok": True, "task": task["title"]})


async def _todo_delete(args: dict) -> str:
    from nexus.core.data.tasks import TodoData
    slug = args["project_slug"]
    todo = TodoData(_data_dir(slug))
    task_id = args["task_id"]
    lst, task = todo.find_task(task_id)
    if task is None:
        return json.dumps({"error": f"Task {task_id!r} not found."})
    todo.delete_task(lst["id"], task_id)
    return json.dumps({"ok": True})


registry.register(
    scope="tasks",
    name="tasks_add",
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
    scope="tasks",
    name="tasks_list",
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
    scope="tasks",
    name="tasks_complete",
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
    scope="tasks",
    name="tasks_delete",
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
