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
            heading = ""
            for line in p.read_text(errors="replace").splitlines():
                if line.startswith("#"):
                    heading = line.lstrip("#").strip()
                    break
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
        path.write_text(text, encoding="utf-8")
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
