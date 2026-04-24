from __future__ import annotations
import asyncio
import json
from datetime import datetime
from pathlib import Path

from nexus.ai.skill_registry import registry
from nexus.core.config_manager import load_project_config
from nexus.core.logger import get

log = get("skills.journal")

_TEX_TEMPLATE = r"""\documentclass{{article}}
\usepackage{{fontenc}}
\usepackage{{inputenc}}
\usepackage{{parskip}}
\title{{{title}}}
\author{{{author}}}
\date{{{date}}}
\begin{{document}}
\maketitle

{content}

\end{{document}}
"""


def _journal_dir(slug: str) -> Path | None:
    cfg = load_project_config(slug)
    raw = cfg.get("journal", {}).get("journal_dir", "")
    if not raw:
        return None
    return Path(raw).expanduser()


def _author(slug: str) -> str:
    return load_project_config(slug).get("journal", {}).get("author", "")


# ---------------------------------------------------------------------------
# journal_list_entries
# ---------------------------------------------------------------------------

async def _journal_list_entries(args: dict) -> str:
    slug = args["project_slug"]
    d    = _journal_dir(slug)
    if d is None or not d.exists():
        return json.dumps({"entries": [], "note": "Journal directory not configured or missing"})
    try:
        entries_dir = d / "entries"
        files = sorted(entries_dir.rglob("*.tex"), reverse=True) if entries_dir.exists() else []
        return json.dumps({"entries": [str(f.relative_to(d)) for f in files]})
    except Exception as exc:
        log.exception("journal_list_entries skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "journal",
    name        = "journal_list_entries",
    description = "List all journal entries (.tex files) sorted newest-first.",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _journal_list_entries,
)


# ---------------------------------------------------------------------------
# journal_new_entry
# ---------------------------------------------------------------------------

async def _journal_new_entry(args: dict) -> str:
    slug    = args["project_slug"]
    content = args.get("content", "")
    d       = _journal_dir(slug)
    if d is None:
        return json.dumps({"error": "Journal directory not configured"})
    try:
        now  = datetime.now()
        year = now.strftime("%Y")
        date = now.strftime("%Y-%m-%d")
        entry_dir = d / "entries" / year
        entry_dir.mkdir(parents=True, exist_ok=True)
        path = entry_dir / f"{date}.tex"
        author = _author(slug)
        text = _TEX_TEMPLATE.format(title=f"Journal — {date}", author=author,
                                     date=date, content=content)
        path.write_text(text, encoding="utf-8")
        return json.dumps({"success": True, "path": str(path)})
    except Exception as exc:
        log.exception("journal_new_entry skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "journal",
    name        = "journal_new_entry",
    description = "Create a new journal entry for today as a LaTeX .tex file.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "content":      {"type": "string", "description": "Body text of the journal entry"},
        },
        "required": ["project_slug"],
    },
    handler = _journal_new_entry,
)


# ---------------------------------------------------------------------------
# journal_compile
# ---------------------------------------------------------------------------

async def _journal_compile(args: dict) -> str:
    slug = args["project_slug"]
    d    = _journal_dir(slug)
    if d is None or not d.exists():
        return json.dumps({"error": "Journal directory not configured or missing"})
    try:
        entries_dir = d / "entries"
        files = sorted(entries_dir.rglob("*.tex"), reverse=True) if entries_dir.exists() else []
        if not files:
            return json.dumps({"error": "No .tex entries found"})
        latest = files[0]
        proc = await asyncio.create_subprocess_exec(
            "pdflatex", "-interaction=nonstopmode", str(latest),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            cwd=str(d),
        )
        out, _ = await proc.communicate()
        return json.dumps({"output": out.decode(errors="replace").strip(),
                           "returncode": proc.returncode, "compiled": str(latest)})
    except FileNotFoundError:
        return json.dumps({"error": "pdflatex not found on PATH"})
    except Exception as exc:
        log.exception("journal_compile skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "journal",
    name        = "journal_compile",
    description = "Compile the most recent journal entry with pdflatex.",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _journal_compile,
)
