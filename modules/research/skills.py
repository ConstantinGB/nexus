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
                text  = await asyncio.to_thread(p.read_text, errors="replace")
                first = text.splitlines()[0] if text.splitlines() else ""
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
        if not path.resolve().is_relative_to(d.resolve()):
            return json.dumps({"error": "filename must not escape the notes directory"})
        await asyncio.to_thread(path.write_text, content, encoding="utf-8")
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


# ---------------------------------------------------------------------------
# research_get_note
# ---------------------------------------------------------------------------

async def _research_get_note(args: dict) -> str:
    slug     = args["project_slug"]
    filename = args["filename"]
    d        = _notes_dir(slug)
    if d is None:
        return json.dumps({"error": "Notes directory not configured"})
    if not filename.endswith(".md"):
        filename += ".md"
    path = d / filename
    if not path.resolve().is_relative_to(d.resolve()):
        return json.dumps({"error": "filename must not escape the notes directory"})
    if not path.exists():
        return json.dumps({"error": f"Note not found: {filename}"})
    try:
        content = await asyncio.to_thread(path.read_text, errors="replace")
        return json.dumps({"filename": filename, "content": content})
    except Exception as exc:
        log.exception("research_get_note skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "research",
    name        = "research_get_note",
    description = "Read and return the full content of a named note.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "filename":     {"type": "string", "description": "Note filename (with or without .md)"},
        },
        "required": ["project_slug", "filename"],
    },
    handler = _research_get_note,
)


# ---------------------------------------------------------------------------
# research_delete_note
# ---------------------------------------------------------------------------

async def _research_delete_note(args: dict) -> str:
    slug     = args["project_slug"]
    filename = args["filename"]
    d        = _notes_dir(slug)
    if d is None:
        return json.dumps({"error": "Notes directory not configured"})
    if not filename.endswith(".md"):
        filename += ".md"
    path = d / filename
    if not path.resolve().is_relative_to(d.resolve()):
        return json.dumps({"error": "filename must not escape the notes directory"})
    if not path.exists():
        return json.dumps({"error": f"Note not found: {filename}"})
    try:
        await asyncio.to_thread(path.unlink)
        return json.dumps({"success": True, "deleted": filename})
    except Exception as exc:
        log.exception("research_delete_note skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "research",
    name        = "research_delete_note",
    description = "Delete a note file by name. Returns an error if the file does not exist.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "filename":     {"type": "string", "description": "Note filename (with or without .md)"},
        },
        "required": ["project_slug", "filename"],
    },
    handler = _research_delete_note,
)


# ---------------------------------------------------------------------------
# AI helpers
# ---------------------------------------------------------------------------

async def _ai_process(content: str, system_prompt: str) -> str:
    from nexus.core.config_manager import is_ai_configured
    if not is_ai_configured():
        return json.dumps({"error": "AI not configured"})
    from nexus.ai.client import AIClient
    try:
        result = await AIClient().chat(
            messages=[{"role": "user", "content": content}],
            system_prompt=system_prompt,
            skill_scopes=[],
        )
        return json.dumps({"result": result})
    except Exception as exc:
        log.exception("AI processing failed")
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# research_summarize_note
# ---------------------------------------------------------------------------

async def _research_summarize_note(args: dict) -> str:
    slug     = args["project_slug"]
    filename = args["filename"]
    d        = _notes_dir(slug)
    if d is None:
        return json.dumps({"error": "Notes directory not configured"})
    if not filename.endswith(".md"):
        filename += ".md"
    path = d / filename
    if not path.resolve().is_relative_to(d.resolve()):
        return json.dumps({"error": "filename must not escape the notes directory"})
    if not path.exists():
        return json.dumps({"error": f"Note not found: {filename}"})
    content = await asyncio.to_thread(path.read_text, errors="replace")
    return await _ai_process(
        content,
        "Summarize the following research note concisely. Preserve all key facts and findings.",
    )


registry.register(
    scope       = "research",
    name        = "research_summarize_note",
    description = "Summarize a research note file using AI.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "filename":     {"type": "string", "description": "Note filename (with or without .md)"},
        },
        "required": ["project_slug", "filename"],
    },
    handler = _research_summarize_note,
)


# ---------------------------------------------------------------------------
# research_clean_note
# ---------------------------------------------------------------------------

async def _research_clean_note(args: dict) -> str:
    slug     = args["project_slug"]
    filename = args["filename"]
    d        = _notes_dir(slug)
    if d is None:
        return json.dumps({"error": "Notes directory not configured"})
    if not filename.endswith(".md"):
        filename += ".md"
    path = d / filename
    if not path.resolve().is_relative_to(d.resolve()):
        return json.dumps({"error": "filename must not escape the notes directory"})
    if not path.exists():
        return json.dumps({"error": f"Note not found: {filename}"})
    content = await asyncio.to_thread(path.read_text, errors="replace")
    result = await _ai_process(
        content,
        (
            "Clean up the following text: remove HTML artifacts, fix broken formatting, "
            "remove duplicate whitespace, and fix obvious encoding issues. "
            "Do not change the meaning, facts, or structure. Return the cleaned text only."
        ),
    )
    try:
        cleaned = json.loads(result).get("result", "")
        if cleaned:
            await asyncio.to_thread(path.write_text, cleaned, encoding="utf-8")
    except Exception:
        pass
    return result


registry.register(
    scope       = "research",
    name        = "research_clean_note",
    description = "Clean up raw or scraped text in a note (remove HTML artifacts, fix formatting) using AI.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "filename":     {"type": "string", "description": "Note filename (with or without .md)"},
        },
        "required": ["project_slug", "filename"],
    },
    handler = _research_clean_note,
)


# ---------------------------------------------------------------------------
# research_rewrite_note
# ---------------------------------------------------------------------------

async def _research_rewrite_note(args: dict) -> str:
    slug        = args["project_slug"]
    filename    = args["filename"]
    instruction = args.get("instruction", "Improve clarity and readability")
    d           = _notes_dir(slug)
    if d is None:
        return json.dumps({"error": "Notes directory not configured"})
    if not filename.endswith(".md"):
        filename += ".md"
    path = d / filename
    if not path.resolve().is_relative_to(d.resolve()):
        return json.dumps({"error": "filename must not escape the notes directory"})
    if not path.exists():
        return json.dumps({"error": f"Note not found: {filename}"})
    content = await asyncio.to_thread(path.read_text, errors="replace")
    result = await _ai_process(
        content,
        (
            f"Rewrite the following note. Instruction: {instruction}. "
            "IMPORTANT: Do not alter any facts, data, or conclusions. "
            "Keep all information exactly as-is — only improve the presentation. "
            "Return the rewritten note in Markdown."
        ),
    )
    try:
        rewritten = json.loads(result).get("result", "")
        if rewritten:
            await asyncio.to_thread(path.write_text, rewritten, encoding="utf-8")
    except Exception:
        pass
    return result


registry.register(
    scope       = "research",
    name        = "research_rewrite_note",
    description = "Rewrite a note for clarity while preserving all facts unchanged.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "filename":     {"type": "string", "description": "Note filename (with or without .md)"},
            "instruction":  {"type": "string", "description": "Rewrite instruction (default: improve clarity)"},
        },
        "required": ["project_slug", "filename"],
    },
    handler = _research_rewrite_note,
)


# ---------------------------------------------------------------------------
# research_search_news
# ---------------------------------------------------------------------------

async def _research_search_news(args: dict) -> str:
    slug  = args["project_slug"]
    query = args["query"]
    cfg   = load_project_config(slug)
    api_key = (
        cfg.get("research", {}).get("news_api_key", "")
        or __import__("os").environ.get("NEWS_API_KEY", "")
    )
    if not api_key:
        return json.dumps({"error": "News API key not configured for this project"})
    try:
        from modules.research.api_client import search_news
        results = await search_news(query, api_key)
        return json.dumps({"results": results, "count": len(results)})
    except Exception as exc:
        log.exception("research_search_news skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "research",
    name        = "research_search_news",
    description = "Search NewsAPI for articles matching a query. Returns up to 10 article metadata records.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "query":        {"type": "string", "description": "News search query"},
        },
        "required": ["project_slug", "query"],
    },
    handler = _research_search_news,
)


# ---------------------------------------------------------------------------
# research_search_wiki
# ---------------------------------------------------------------------------

async def _research_search_wiki(args: dict) -> str:
    query    = args["query"]
    language = args.get("language", "en")
    try:
        from modules.research.api_client import search_wiki
        results = await search_wiki(query, language=language)
        return json.dumps({"results": results, "count": len(results)})
    except Exception as exc:
        log.exception("research_search_wiki skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "research",
    name        = "research_search_wiki",
    description = "Search Wikipedia for articles matching a query. Returns titles, summaries, and URLs.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "query":        {"type": "string", "description": "Wikipedia search query"},
            "language":     {"type": "string", "description": "Wikipedia language code (default: en)"},
        },
        "required": ["project_slug", "query"],
    },
    handler = _research_search_wiki,
)
