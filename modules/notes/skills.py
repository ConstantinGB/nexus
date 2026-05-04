from __future__ import annotations
import json
from pathlib import Path

from nexus.ai.skill_registry import registry

_PROJECTS_ROOT = Path(__file__).parent.parent.parent / "projects"


def _data_dir(slug: str) -> Path:
    return _PROJECTS_ROOT / slug / "data" / "notes"


async def _note_create(args: dict) -> str:
    from nexus.core.data.notes import NotesData
    slug = args["project_slug"]
    notes = NotesData(_data_dir(slug))
    note = notes.create_note(
        title=args["title"],
        content=args.get("content", ""),
        tags=args.get("tags", []),
    )
    return json.dumps({"ok": True, "note_id": note["id"], "file": note["file"]})


async def _note_search(args: dict) -> str:
    from nexus.core.data.notes import NotesData
    slug = args["project_slug"]
    notes = NotesData(_data_dir(slug))
    results = notes.search(args["query"])
    return json.dumps({"results": results})


async def _note_get(args: dict) -> str:
    from nexus.core.data.notes import NotesData
    slug = args["project_slug"]
    notes = NotesData(_data_dir(slug))
    content = notes.get_content(args["note_id"])
    meta = notes.get_by_id(args["note_id"])
    return json.dumps({"meta": meta, "content": content})


async def _note_update(args: dict) -> str:
    from nexus.core.data.notes import NotesData
    slug = args["project_slug"]
    notes = NotesData(_data_dir(slug))
    notes.update_note(args["note_id"], args["content"])
    return json.dumps({"ok": True})


async def _note_delete(args: dict) -> str:
    from nexus.core.data.notes import NotesData
    slug = args["project_slug"]
    notes = NotesData(_data_dir(slug))
    notes.delete_note(args["note_id"])
    return json.dumps({"ok": True})


registry.register(
    scope="notes",
    name="notes_create",
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
    scope="notes",
    name="notes_search",
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
    scope="notes",
    name="notes_get",
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
    scope="notes",
    name="notes_update",
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
    scope="notes",
    name="notes_delete",
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
