from __future__ import annotations
import asyncio
import json
from pathlib import Path

from nexus.ai.skill_registry import registry
from nexus.core.config_manager import load_project_config
from nexus.core.logger import get

log = get("skills.research")


def _notes_dir(slug: str) -> Path | None:
    cfg = load_project_config(slug)
    raw = cfg.get("research", {}).get("notes_dir", "")
    if not raw:
        return None
    return Path(raw).expanduser()


# ---------------------------------------------------------------------------
# research_list_notes
# ---------------------------------------------------------------------------

async def _research_list_notes(args: dict) -> str:
    slug = args["project_slug"]
    d    = _notes_dir(slug)
    if d is None or not d.exists():
        return json.dumps({"notes": [], "note": "Notes directory not configured or missing"})
    try:
        notes = []
        for p in sorted(d.glob("*.md")):
            try:
                first = p.read_text(errors="replace").splitlines()[0]
            except Exception:
                first = ""
            notes.append({"filename": p.name, "first_line": first})
        return json.dumps({"notes": notes})
    except Exception as exc:
        log.exception("research_list_notes skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "research",
    name        = "research_list_notes",
    description = "List all Markdown notes in the research notes directory with their first line.",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _research_list_notes,
)


# ---------------------------------------------------------------------------
# research_new_note
# ---------------------------------------------------------------------------

async def _research_new_note(args: dict) -> str:
    slug     = args["project_slug"]
    filename = args["filename"].rstrip("/")
    content  = args["content"]
    d        = _notes_dir(slug)
    if d is None:
        return json.dumps({"error": "Notes directory not configured"})
    try:
        d.mkdir(parents=True, exist_ok=True)
        if not filename.endswith(".md"):
            filename += ".md"
        path = d / filename
        path.write_text(content, encoding="utf-8")
        return json.dumps({"success": True, "path": str(path)})
    except Exception as exc:
        log.exception("research_new_note skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "research",
    name        = "research_new_note",
    description = "Create a new Markdown note in the research notes directory.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "filename":     {"type": "string", "description": "Note filename (without path; .md appended if missing)"},
            "content":      {"type": "string", "description": "Full Markdown content of the note"},
        },
        "required": ["project_slug", "filename", "content"],
    },
    handler = _research_new_note,
)


# ---------------------------------------------------------------------------
# research_search
# ---------------------------------------------------------------------------

async def _research_search(args: dict) -> str:
    slug  = args["project_slug"]
    query = args["query"]
    d     = _notes_dir(slug)
    if d is None or not d.exists():
        return json.dumps({"error": "Notes directory not configured or missing"})
    try:
        proc = await asyncio.create_subprocess_exec(
            "grep", "-rn", query, str(d),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await proc.communicate()
        return json.dumps({"output": out.decode(errors="replace").strip(),
                           "returncode": proc.returncode})
    except FileNotFoundError:
        return json.dumps({"error": "grep not found on PATH"})
    except Exception as exc:
        log.exception("research_search skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "research",
    name        = "research_search",
    description = "Search all research notes for a query string (case-sensitive grep -rn).",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "query":        {"type": "string", "description": "Search string"},
        },
        "required": ["project_slug", "query"],
    },
    handler = _research_search,
)
