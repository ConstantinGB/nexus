from __future__ import annotations
import asyncio
import json
from datetime import datetime
from pathlib import Path

from nexus.ai.skill_registry import registry
from nexus.core.config_manager import load_project_config
from nexus.core.logger import get

log = get("skills.org")

_WEEKLY_TABLE = """\
| Time  | Monday | Tuesday | Wednesday | Thursday | Friday | Saturday | Sunday |
|-------|--------|---------|-----------|----------|--------|----------|--------|
| 08:00 |        |         |           |          |        |          |        |
| 09:00 |        |         |           |          |        |          |        |
| 10:00 |        |         |           |          |        |          |        |
| 11:00 |        |         |           |          |        |          |        |
| 12:00 |        |         |           |          |        |          |        |
| 13:00 |        |         |           |          |        |          |        |
| 14:00 |        |         |           |          |        |          |        |
| 15:00 |        |         |           |          |        |          |        |
| 16:00 |        |         |           |          |        |          |        |
| 17:00 |        |         |           |          |        |          |        |
"""


def _output_dir(slug: str) -> Path | None:
    cfg = load_project_config(slug)
    raw = cfg.get("org", {}).get("output_dir", "")
    if not raw:
        return None
    return Path(raw).expanduser()


# ---------------------------------------------------------------------------
# org_list_plans
# ---------------------------------------------------------------------------

async def _org_list_plans(args: dict) -> str:
    slug = args["project_slug"]
    d    = _output_dir(slug)
    if d is None or not d.exists():
        return json.dumps({"plans": [], "note": "Output directory not configured or missing"})
    try:
        files = await asyncio.to_thread(lambda: sorted(
            d.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True
        ))
        return json.dumps({"plans": [f.name for f in files]})
    except Exception as exc:
        log.exception("org_list_plans skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "org",
    name        = "org_list_plans",
    description = "List all plan/diagram/schedule Markdown files sorted by most recently modified.",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _org_list_plans,
)


# ---------------------------------------------------------------------------
# org_new_plan
# ---------------------------------------------------------------------------

async def _org_new_plan(args: dict) -> str:
    slug  = args["project_slug"]
    name  = args["name"]
    tasks = args.get("tasks", [])
    d     = _output_dir(slug)
    if d is None:
        return json.dumps({"error": "Output directory not configured"})
    try:
        d.mkdir(parents=True, exist_ok=True)
        date     = datetime.now().strftime("%Y-%m-%d")
        filename = name.lower().replace(" ", "-").replace("/", "-")[:50] + ".md"
        items    = "\n".join(f"- [ ] {t}" for t in tasks) if tasks else "- [ ] "
        text     = f"# {name}\n\n_Created: {date}_\n\n## Tasks\n\n{items}\n"
        path     = d / filename
        path.write_text(text, encoding="utf-8")
        return json.dumps({"success": True, "path": str(path)})
    except Exception as exc:
        log.exception("org_new_plan skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "org",
    name        = "org_new_plan",
    description = "Create a new plan Markdown file with a task checklist.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "name":         {"type": "string", "description": "Plan title"},
            "tasks":        {"type": "array", "items": {"type": "string"},
                             "description": "List of task strings for the checklist"},
        },
        "required": ["project_slug", "name"],
    },
    handler = _org_new_plan,
)


# ---------------------------------------------------------------------------
# org_new_diagram
# ---------------------------------------------------------------------------

async def _org_new_diagram(args: dict) -> str:
    slug            = args["project_slug"]
    name            = args["name"]
    mermaid_content = args.get("mermaid_content", "flowchart LR\n    A --> B")
    d               = _output_dir(slug)
    if d is None:
        return json.dumps({"error": "Output directory not configured"})
    try:
        d.mkdir(parents=True, exist_ok=True)
        filename = name.lower().replace(" ", "-").replace("/", "-")[:50] + ".md"
        text     = f"# {name}\n\n```mermaid\n{mermaid_content}\n```\n"
        path     = d / filename
        path.write_text(text, encoding="utf-8")
        return json.dumps({"success": True, "path": str(path)})
    except Exception as exc:
        log.exception("org_new_diagram skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "org",
    name        = "org_new_diagram",
    description = "Create a Markdown file containing a Mermaid diagram.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug":    {"type": "string"},
            "name":            {"type": "string", "description": "Diagram title"},
            "mermaid_content": {"type": "string",
                                "description": "Mermaid diagram source (without the ``` fences)"},
        },
        "required": ["project_slug", "name"],
    },
    handler = _org_new_diagram,
)


# ---------------------------------------------------------------------------
# org_new_schedule
# ---------------------------------------------------------------------------

async def _org_new_schedule(args: dict) -> str:
    slug = args["project_slug"]
    name = args["name"]
    d    = _output_dir(slug)
    if d is None:
        return json.dumps({"error": "Output directory not configured"})
    try:
        d.mkdir(parents=True, exist_ok=True)
        date     = datetime.now().strftime("%Y-%m-%d")
        filename = name.lower().replace(" ", "-").replace("/", "-")[:50] + ".md"
        text     = f"# {name}\n\n_Created: {date}_\n\n{_WEEKLY_TABLE}"
        path     = d / filename
        path.write_text(text, encoding="utf-8")
        return json.dumps({"success": True, "path": str(path)})
    except Exception as exc:
        log.exception("org_new_schedule skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "org",
    name        = "org_new_schedule",
    description = "Create a weekly schedule Markdown file with an hourly time-slot table.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "name":         {"type": "string", "description": "Schedule title"},
        },
        "required": ["project_slug", "name"],
    },
    handler = _org_new_schedule,
)
