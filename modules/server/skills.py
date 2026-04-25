from __future__ import annotations
import asyncio
import json

from nexus.ai.skill_registry import registry
from nexus.core.config_manager import load_project_config
from nexus.core.logger import get

log = get("skills.server")


def _server_cfg(slug: str) -> dict:
    return load_project_config(slug).get("server", {})


def _find_service(cfg: dict, name: str) -> dict | None:
    return next((s for s in cfg.get("services", []) if s.get("name") == name), None)


# ---------------------------------------------------------------------------
# server_list_services
# ---------------------------------------------------------------------------

async def _server_list_services(args: dict) -> str:
    slug     = args["project_slug"]
    cfg      = _server_cfg(slug)
    services = cfg.get("services", [])
    return json.dumps({"services": services})


registry.register(
    scope       = "server",
    name        = "server_list_services",
    description = "List all registered services for a Server project (name, port, type).",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _server_list_services,
)


# ---------------------------------------------------------------------------
# server_status
# ---------------------------------------------------------------------------

async def _server_status(args: dict) -> str:
    slug    = args["project_slug"]
    svc_name = args["service"]
    cfg     = _server_cfg(slug)
    svc     = _find_service(cfg, svc_name)
    if svc is None:
        return json.dumps({"error": f"Service '{svc_name}' not found in project"})
    svc_type = svc.get("type", "docker")
    try:
        if svc_type == "systemd":
            cmd = ["systemctl", "is-active", svc_name]
        else:
            cmd = ["docker", "inspect", "--format={{.State.Status}}", svc_name]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await proc.communicate()
        status = out.decode().strip() or "unknown"
        return json.dumps({"service": svc_name, "type": svc_type, "status": status})
    except FileNotFoundError as exc:
        return json.dumps({"error": f"Command not found: {exc.filename}"})
    except Exception as exc:
        log.exception("server_status skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "server",
    name        = "server_status",
    description = "Get the running status of a service (systemd: is-active; docker: container state).",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "service":      {"type": "string", "description": "Service name"},
        },
        "required": ["project_slug", "service"],
    },
    handler = _server_status,
)


# ---------------------------------------------------------------------------
# server_start / server_stop
# ---------------------------------------------------------------------------

async def _service_action(slug: str, svc_name: str, action: str) -> str:
    cfg      = _server_cfg(slug)
    svc      = _find_service(cfg, svc_name)
    if svc is None:
        return json.dumps({"error": f"Service '{svc_name}' not found in project"})
    svc_type = svc.get("type", "docker")
    if svc_type == "systemd":
        cmd = ["systemctl", action, svc_name]
    else:
        cmd = ["docker", action, svc_name]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await proc.communicate()
        return json.dumps({"success": proc.returncode == 0,
                           "output": out.decode(errors="replace").strip()})
    except FileNotFoundError as exc:
        return json.dumps({"error": f"Command not found: {exc.filename}"})
    except Exception as exc:
        log.exception("server_%s skill failed for %s", action, svc_name)
        return json.dumps({"error": str(exc)})


async def _server_start(args: dict) -> str:
    return await _service_action(args["project_slug"], args["service"], "start")


async def _server_stop(args: dict) -> str:
    return await _service_action(args["project_slug"], args["service"], "stop")


async def _server_restart(args: dict) -> str:
    return await _service_action(args["project_slug"], args["service"], "restart")


for _action, _handler, _desc in [
    ("start",   _server_start,   "Start a service (systemctl start or docker start)."),
    ("stop",    _server_stop,    "Stop a service (systemctl stop or docker stop)."),
    ("restart", _server_restart, "Restart a service (systemctl restart or docker restart)."),
]:
    registry.register(
        scope       = "server",
        name        = f"server_{_action}",
        description = _desc,
        schema      = {
            "type": "object",
            "properties": {
                "project_slug": {"type": "string"},
                "service":      {"type": "string", "description": "Service name"},
            },
            "required": ["project_slug", "service"],
        },
        handler = _handler,
    )
