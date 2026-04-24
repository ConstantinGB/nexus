from __future__ import annotations
import json
from pathlib import Path

from nexus.ai.skill_registry import registry
from nexus.core.logger import get

log = get("skills.global")

_ROOT     = Path(__file__).parent.parent.parent
_LOG_FILE = _ROOT / "logs" / "nexus.log"


# ---------------------------------------------------------------------------
# list_projects
# ---------------------------------------------------------------------------

async def _list_projects(args: dict) -> str:
    try:
        from nexus.core.project_manager import list_projects
        projects = list_projects()
        return json.dumps([
            {"name": p.name, "slug": p.slug, "module": p.module, "description": p.description}
            for p in projects
        ])
    except Exception as exc:
        log.exception("list_projects skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "global",
    name        = "list_projects",
    description = "List all Nexus projects with their name, slug, module type, and description.",
    schema      = {"type": "object", "properties": {}, "required": []},
    handler     = _list_projects,
)


# ---------------------------------------------------------------------------
# run_flow
# ---------------------------------------------------------------------------

async def _run_flow(args: dict) -> str:
    action = args["action"]
    try:
        payload = json.loads(args.get("payload") or "{}")
    except json.JSONDecodeError:
        return json.dumps({"error": "payload must be valid JSON"})
    from nexus.core.mycelium import bus
    try:
        result = await bus.send(action, payload)
        return result if isinstance(result, str) else json.dumps({"result": result})
    except NotImplementedError:
        available = [f.action for f in bus.all_flows()]
        return json.dumps({"error": f"No handler registered for '{action}'", "available": available})
    except Exception as exc:
        log.exception("run_flow failed for action=%s", action)
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "global",
    name        = "run_flow",
    description = "Trigger a Mycelium cross-module flow by action name (e.g. 'research_to_codex').",
    schema      = {
        "type": "object",
        "properties": {
            "action":  {"type": "string", "description": "Mycelium flow action identifier"},
            "payload": {"type": "string", "description": "JSON-encoded payload for the flow"},
        },
        "required": ["action"],
    },
    handler = _run_flow,
)


# ---------------------------------------------------------------------------
# search_logs
# ---------------------------------------------------------------------------

async def _search_logs(args: dict) -> str:
    query = args.get("query", "")
    n     = int(args.get("n", 50))
    try:
        if not _LOG_FILE.exists():
            return json.dumps({"lines": [], "note": "Log file not found"})
        lines = _LOG_FILE.read_text(errors="replace").splitlines()
        if query:
            lines = [l for l in lines if query.lower() in l.lower()]
        return json.dumps({"lines": lines[-n:]})
    except Exception as exc:
        log.exception("search_logs skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "global",
    name        = "search_logs",
    description = "Return recent log lines from nexus.log, optionally filtered by a search query.",
    schema      = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Case-insensitive substring to filter lines (optional)"},
            "n":     {"type": "integer", "description": "Maximum number of lines to return (default 50)"},
        },
        "required": [],
    },
    handler = _search_logs,
)
