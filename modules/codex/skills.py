from __future__ import annotations

import asyncio
import json
from pathlib import Path

from nexus.ai.skill_registry import registry
from nexus.core.logger import get

log = get("skills.codex")


def _project_info(slug: str):
    from nexus.core.project_manager import list_projects
    for p in list_projects():
        if p.slug == slug:
            return p
    return None


def _get_sources(slug: str) -> dict[str, list[Path]]:
    from modules.codex.project_screen import _get_codex_sources
    project = _project_info(slug)
    if project is None:
        return {}
    return _get_codex_sources(project)


# ---------------------------------------------------------------------------
# codex_list
# ---------------------------------------------------------------------------

async def _codex_list(args: dict) -> str:
    slug = args["project_slug"]
    try:
        sources = await asyncio.to_thread(_get_sources, slug)
        result = {}
        for src, files in sources.items():
            result[src] = [f.name for f in files]
        total = sum(len(v) for v in result.values())
        return json.dumps({"sources": result, "total": total})
    except Exception as exc:
        log.exception("codex_list skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "codex",
    name        = "codex_list",
    description = "List all source files available in the Codex (Journal, Notes, Research, Org, YouTube), grouped by module.",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _codex_list,
)


# ---------------------------------------------------------------------------
# codex_search
# ---------------------------------------------------------------------------

async def _codex_search(args: dict) -> str:
    slug  = args["project_slug"]
    query = args["query"]
    try:
        sources = await asyncio.to_thread(_get_sources, slug)
        all_files = [str(f) for files in sources.values() for f in files]
        if not all_files:
            return json.dumps({"output": "No source files found.", "returncode": 0})
        proc = await asyncio.create_subprocess_exec(
            "grep", "-rn", "--include=*.md", "--include=*.tex", "--include=*.txt",
            query, *all_files,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await proc.communicate()
        return json.dumps({
            "output": out.decode(errors="replace").strip(),
            "returncode": proc.returncode,
        })
    except FileNotFoundError:
        return json.dumps({"error": "grep not found on PATH"})
    except Exception as exc:
        log.exception("codex_search skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "codex",
    name        = "codex_search",
    description = "Search all Codex source files (Journal, Notes, Research, Org, YouTube) for a query string.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "query":        {"type": "string"},
        },
        "required": ["project_slug", "query"],
    },
    handler = _codex_search,
)


# ---------------------------------------------------------------------------
# codex_get_file
# ---------------------------------------------------------------------------

async def _codex_get_file(args: dict) -> str:
    slug     = args["project_slug"]
    filename = args["filename"]
    try:
        sources = await asyncio.to_thread(_get_sources, slug)
        all_files = [f for files in sources.values() for f in files]
        match = next((f for f in all_files if f.name == filename), None)
        if match is None:
            return json.dumps({"error": f"File not found: {filename}"})
        content = await asyncio.to_thread(match.read_text, errors="replace")
        return json.dumps({"filename": filename, "content": content})
    except Exception as exc:
        log.exception("codex_get_file skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "codex",
    name        = "codex_get_file",
    description = "Read and return the full content of a named file from any Codex source (Journal, Notes, Research, Org, YouTube).",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "filename":     {"type": "string", "description": "Exact filename (e.g. 'entry.tex', 'note.md')"},
        },
        "required": ["project_slug", "filename"],
    },
    handler = _codex_get_file,
)
