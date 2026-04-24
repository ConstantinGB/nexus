from __future__ import annotations
import asyncio
import json

from nexus.ai.skill_registry import registry
from nexus.core.config_manager import load_project_config
from nexus.core.logger import get

log = get("skills.home")


def _home_cfg(slug: str) -> dict:
    return load_project_config(slug).get("home", {})


# ---------------------------------------------------------------------------
# home_ping
# ---------------------------------------------------------------------------

async def _home_ping(args: dict) -> str:
    slug = args["project_slug"]
    cfg  = _home_cfg(slug)
    url  = cfg.get("ha_url", "")
    if not url:
        return json.dumps({"error": "ha_url not configured"})
    try:
        proc = await asyncio.create_subprocess_exec(
            "curl", "-sf", "--max-time", "5", url,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await proc.communicate()
        reachable = proc.returncode == 0
        return json.dumps({"reachable": reachable, "returncode": proc.returncode,
                           "output": out.decode(errors="replace").strip()[:500]})
    except FileNotFoundError:
        return json.dumps({"error": "curl not found on PATH"})
    except Exception as exc:
        log.exception("home_ping skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "home",
    name        = "home_ping",
    description = "Ping the Home Assistant URL to check if it is reachable.",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _home_ping,
)


# ---------------------------------------------------------------------------
# home_api_call
# ---------------------------------------------------------------------------

async def _home_api_call(args: dict) -> str:
    slug     = args["project_slug"]
    endpoint = args["endpoint"].lstrip("/")
    method   = args.get("method", "GET").upper()
    cfg      = _home_cfg(slug)
    url      = cfg.get("ha_url", "").rstrip("/")
    token    = cfg.get("token", "")
    if not url:
        return json.dumps({"error": "ha_url not configured"})
    full_url = f"{url}/{endpoint}"
    cmd = ["curl", "-sf", "--max-time", "10", "-X", method,
           "-H", f"Authorization: Bearer {token}",
           "-H", "Content-Type: application/json",
           full_url]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await proc.communicate()
        return json.dumps({"output": out.decode(errors="replace").strip(),
                           "returncode": proc.returncode})
    except FileNotFoundError:
        return json.dumps({"error": "curl not found on PATH"})
    except Exception as exc:
        log.exception("home_api_call skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "home",
    name        = "home_api_call",
    description = "Call a Home Assistant REST API endpoint using the configured token.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "endpoint":     {"type": "string",
                             "description": "API path relative to HA base URL, e.g. 'api/states'"},
            "method":       {"type": "string", "description": "HTTP method (default GET)"},
        },
        "required": ["project_slug", "endpoint"],
    },
    handler = _home_api_call,
)
