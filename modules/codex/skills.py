from __future__ import annotations
import asyncio
import json
from datetime import datetime
from pathlib import Path

from nexus.ai.skill_registry import registry
from nexus.core.config_manager import load_project_config
from nexus.core.logger import get

log = get("skills.codex")


def _vault_dir(slug: str) -> Path | None:
    cfg = load_project_config(slug)
    raw = cfg.get("codex", {}).get("vault_dir", "")
    if not raw:
        return None
    return Path(raw).expanduser()


# ---------------------------------------------------------------------------
# codex_list
# ---------------------------------------------------------------------------

async def _codex_list(args: dict) -> str:
    slug = args["project_slug"]
    d    = _vault_dir(slug)
    if d is None or not d.exists():
        return json.dumps({"entries": [], "note": "Vault directory not configured or missing"})
    try:
        entries = []
        for p in sorted(d.rglob("*.md")):
            try:
                text    = await asyncio.to_thread(p.read_text, errors="replace")
                heading = ""
                for line in text.splitlines():
                    if line.startswith("#"):
                        heading = line.lstrip("#").strip()
                        break
            except Exception:
                heading = ""
            entries.append({"filename": str(p.relative_to(d)), "heading": heading})
        return json.dumps({"entries": entries, "count": len(entries)})
    except Exception as exc:
        log.exception("codex_list skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "codex",
    name        = "codex_list",
    description = "List all Markdown entries in the Codex vault with their first heading.",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _codex_list,
)


# ---------------------------------------------------------------------------
# codex_new_entry
# ---------------------------------------------------------------------------

_FRONTMATTER = """\
---
id: {date_id}
title: {title}
date: {date}
tags: []
---

# {title}

{content}
"""


async def _codex_new_entry(args: dict) -> str:
    slug    = args["project_slug"]
    title   = args["title"]
    content = args.get("content", "")
    d       = _vault_dir(slug)
    if d is None:
        return json.dumps({"error": "Vault directory not configured"})
    try:
        d.mkdir(parents=True, exist_ok=True)
        now     = datetime.now()
        date_id = now.strftime("%Y%m%d%H%M%S")
        date    = now.strftime("%Y-%m-%d")
        slug_name = title.lower().replace(" ", "-").replace("/", "-")[:50]
        filename  = f"{date_id}-{slug_name}.md"
        text = _FRONTMATTER.format(date_id=date_id, title=title, date=date, content=content)
        path = d / filename
        await asyncio.to_thread(path.write_text, text, encoding="utf-8")
        return json.dumps({"success": True, "path": str(path)})
    except Exception as exc:
        log.exception("codex_new_entry skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "codex",
    name        = "codex_new_entry",
    description = "Create a new Zettelkasten entry in the Codex vault with date-based ID frontmatter.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "title":        {"type": "string", "description": "Entry title"},
            "content":      {"type": "string", "description": "Body content (Markdown)"},
        },
        "required": ["project_slug", "title"],
    },
    handler = _codex_new_entry,
)


# ---------------------------------------------------------------------------
# codex_search
# ---------------------------------------------------------------------------

async def _codex_search(args: dict) -> str:
    slug  = args["project_slug"]
    query = args["query"]
    d     = _vault_dir(slug)
    if d is None or not d.exists():
        return json.dumps({"error": "Vault directory not configured or missing"})
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
        log.exception("codex_search skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "codex",
    name        = "codex_search",
    description = "Search all Codex vault entries for a query string (grep -rn).",
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
# codex_get_entry
# ---------------------------------------------------------------------------

async def _codex_get_entry(args: dict) -> str:
    slug     = args["project_slug"]
    filename = args["filename"]
    d        = _vault_dir(slug)
    if d is None:
        return json.dumps({"error": "Vault directory not configured"})
    if not filename.endswith(".md"):
        filename += ".md"
    path = d / filename
    if not path.resolve().is_relative_to(d.resolve()):
        return json.dumps({"error": "filename must not escape the vault directory"})
    if not path.exists():
        return json.dumps({"error": f"Entry not found: {filename}"})
    try:
        content = await asyncio.to_thread(path.read_text, errors="replace")
        return json.dumps({"filename": filename, "content": content})
    except Exception as exc:
        log.exception("codex_get_entry skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "codex",
    name        = "codex_get_entry",
    description = "Read and return the full content of a named Codex vault entry.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "filename":     {"type": "string", "description": "Entry filename relative to vault root (with or without .md)"},
        },
        "required": ["project_slug", "filename"],
    },
    handler = _codex_get_entry,
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
        log.exception("AI processing failed in codex skill")
        return json.dumps({"error": str(exc)})


def _get_all_dirs(slug: str) -> list[Path]:
    """Return vault_dir + all connected_dirs for this codex project."""
    cfg = load_project_config(slug)
    mod = cfg.get("codex", {})
    raw = mod.get("vault_dir", "")
    dirs = []
    if raw:
        p = Path(raw).expanduser()
        if p.exists():
            dirs.append(p)
    for craw in mod.get("connected_dirs", []):
        p = Path(craw).expanduser()
        if p.exists() and p not in dirs:
            dirs.append(p)
    return dirs


# ---------------------------------------------------------------------------
# codex_summarize
# ---------------------------------------------------------------------------

async def _codex_summarize(args: dict) -> str:
    slug     = args["project_slug"]
    filename = args["filename"]
    d        = _vault_dir(slug)
    if d is None:
        return json.dumps({"error": "Vault directory not configured"})
    if not filename.endswith(".md"):
        filename += ".md"
    path = d / filename
    if not path.resolve().is_relative_to(d.resolve()):
        return json.dumps({"error": "filename must not escape the vault directory"})
    if not path.exists():
        return json.dumps({"error": f"Entry not found: {filename}"})
    content = await asyncio.to_thread(path.read_text, errors="replace")
    return await _ai_process(
        content,
        "Summarize the following knowledge entry concisely. Preserve all key facts.",
    )


registry.register(
    scope       = "codex",
    name        = "codex_summarize",
    description = "Summarize a Codex vault entry using AI.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "filename":     {"type": "string"},
        },
        "required": ["project_slug", "filename"],
    },
    handler = _codex_summarize,
)


# ---------------------------------------------------------------------------
# codex_clean
# ---------------------------------------------------------------------------

async def _codex_clean(args: dict) -> str:
    slug     = args["project_slug"]
    filename = args["filename"]
    d        = _vault_dir(slug)
    if d is None:
        return json.dumps({"error": "Vault directory not configured"})
    if not filename.endswith(".md"):
        filename += ".md"
    path = d / filename
    if not path.resolve().is_relative_to(d.resolve()):
        return json.dumps({"error": "filename must not escape the vault directory"})
    if not path.exists():
        return json.dumps({"error": f"Entry not found: {filename}"})
    content = await asyncio.to_thread(path.read_text, errors="replace")
    result = await _ai_process(
        content,
        (
            "Clean up the following knowledge note: remove HTML artifacts, fix broken "
            "formatting, remove duplicate whitespace, and fix obvious encoding issues. "
            "Do not change the meaning or structure. Return the cleaned Markdown only."
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
    scope       = "codex",
    name        = "codex_clean",
    description = "Clean up formatting artifacts in a Codex entry using AI.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "filename":     {"type": "string"},
        },
        "required": ["project_slug", "filename"],
    },
    handler = _codex_clean,
)


# ---------------------------------------------------------------------------
# codex_rewrite
# ---------------------------------------------------------------------------

async def _codex_rewrite(args: dict) -> str:
    slug        = args["project_slug"]
    filename    = args["filename"]
    instruction = args.get("instruction", "Improve clarity and readability")
    d           = _vault_dir(slug)
    if d is None:
        return json.dumps({"error": "Vault directory not configured"})
    if not filename.endswith(".md"):
        filename += ".md"
    path = d / filename
    if not path.resolve().is_relative_to(d.resolve()):
        return json.dumps({"error": "filename must not escape the vault directory"})
    if not path.exists():
        return json.dumps({"error": f"Entry not found: {filename}"})
    content = await asyncio.to_thread(path.read_text, errors="replace")
    result = await _ai_process(
        content,
        (
            f"Rewrite the following knowledge note. Instruction: {instruction}. "
            "IMPORTANT: Do not alter any facts, data, or conclusions — only improve "
            "the presentation. Keep all information exactly as-is. "
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
    scope       = "codex",
    name        = "codex_rewrite",
    description = "Rewrite a Codex entry for clarity while preserving all facts unchanged.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "filename":     {"type": "string"},
            "instruction":  {"type": "string", "description": "Rewrite instruction (default: improve clarity)"},
        },
        "required": ["project_slug", "filename"],
    },
    handler = _codex_rewrite,
)


# ---------------------------------------------------------------------------
# codex_restructure
# ---------------------------------------------------------------------------

async def _codex_restructure(args: dict) -> str:
    slug     = args["project_slug"]
    filename = args["filename"]
    d        = _vault_dir(slug)
    if d is None:
        return json.dumps({"error": "Vault directory not configured"})
    if not filename.endswith(".md"):
        filename += ".md"
    path = d / filename
    if not path.resolve().is_relative_to(d.resolve()):
        return json.dumps({"error": "filename must not escape the vault directory"})
    if not path.exists():
        return json.dumps({"error": f"Entry not found: {filename}"})
    content = await asyncio.to_thread(path.read_text, errors="replace")
    result = await _ai_process(
        content,
        (
            "Restructure the following knowledge note by reorganising its headings, "
            "sections, and paragraphs for better logical flow. "
            "Do NOT change any facts, data, or wording beyond what is needed for structure. "
            "Return the restructured Markdown."
        ),
    )
    try:
        restructured = json.loads(result).get("result", "")
        if restructured:
            await asyncio.to_thread(path.write_text, restructured, encoding="utf-8")
    except Exception:
        pass
    return result


registry.register(
    scope       = "codex",
    name        = "codex_restructure",
    description = "Restructure a Codex entry's headings and sections for better flow using AI.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "filename":     {"type": "string"},
        },
        "required": ["project_slug", "filename"],
    },
    handler = _codex_restructure,
)


# ---------------------------------------------------------------------------
# codex_format
# ---------------------------------------------------------------------------

async def _codex_format(args: dict) -> str:
    slug     = args["project_slug"]
    filename = args["filename"]
    d        = _vault_dir(slug)
    if d is None:
        return json.dumps({"error": "Vault directory not configured"})
    if not filename.endswith(".md"):
        filename += ".md"
    path = d / filename
    if not path.resolve().is_relative_to(d.resolve()):
        return json.dumps({"error": "filename must not escape the vault directory"})
    if not path.exists():
        return json.dumps({"error": f"Entry not found: {filename}"})
    content = await asyncio.to_thread(path.read_text, errors="replace")
    result = await _ai_process(
        content,
        (
            "Standardise the Markdown formatting of the following knowledge note: "
            "fix heading levels, normalise bullet points and numbered lists, "
            "ensure consistent spacing, and clean up inline code/bold/italic usage. "
            "Do not change any content. Return the formatted Markdown only."
        ),
    )
    try:
        formatted = json.loads(result).get("result", "")
        if formatted:
            await asyncio.to_thread(path.write_text, formatted, encoding="utf-8")
    except Exception:
        pass
    return result


registry.register(
    scope       = "codex",
    name        = "codex_format",
    description = "Standardise Markdown formatting in a Codex entry using AI.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "filename":     {"type": "string"},
        },
        "required": ["project_slug", "filename"],
    },
    handler = _codex_format,
)


# ---------------------------------------------------------------------------
# codex_answer
# ---------------------------------------------------------------------------

_CHUNK_CHARS = 8000


async def _codex_answer(args: dict) -> str:
    slug     = args["project_slug"]
    question = args["question"]
    dirs     = _get_all_dirs(slug)
    if not dirs:
        return json.dumps({"error": "No vault or connected directories configured"})

    from nexus.core.config_manager import is_ai_configured
    if not is_ai_configured():
        return json.dumps({"error": "AI not configured"})

    # Collect all .md files from vault + connected dirs (deduplicated)
    seen: set[Path] = set()
    all_files: list[Path] = []
    for d in dirs:
        try:
            for p in sorted(d.rglob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
                resolved = p.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    all_files.append(p)
        except Exception:
            pass

    if not all_files:
        return json.dumps({"answer": "No notes found in vault or connected directories."})

    # Build context from all files (chunk if needed)
    parts = []
    total = 0
    for p in all_files:
        try:
            text = await asyncio.to_thread(p.read_text, errors="replace")
            chunk = f"### {p.stem}\n{text[:_CHUNK_CHARS]}\n"
            parts.append(chunk)
            total += len(chunk)
            if total > 60000:
                parts.append("(truncated — too many files)\n")
                break
        except Exception:
            pass

    context = "\n".join(parts)
    from nexus.ai.client import AIClient
    try:
        answer = await AIClient().chat(
            messages=[{"role": "user", "content": f"Question: {question}\n\nKnowledge base:\n{context}"}],
            system_prompt=(
                "You are a knowledge assistant. Answer the user's question using only "
                "the provided knowledge base entries. Cite the note title when relevant. "
                "If the answer is not in the knowledge base, say so clearly."
            ),
            skill_scopes=[],
        )
        return json.dumps({"answer": answer, "files_searched": len(all_files)})
    except Exception as exc:
        log.exception("codex_answer AI call failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "codex",
    name        = "codex_answer",
    description = (
        "Search all connected Codex vault entries and synthesize an answer to a question. "
        "Reads the vault directory plus any connected directories."
    ),
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "question":     {"type": "string", "description": "Question to answer from the knowledge base"},
        },
        "required": ["project_slug", "question"],
    },
    handler = _codex_answer,
)
