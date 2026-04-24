from __future__ import annotations
import asyncio
import json
import shutil

from nexus.ai.skill_registry import registry
from nexus.core.config_manager import load_project_config
from nexus.core.logger import get

log = get("skills.vtube")


def _vtube_cfg(slug: str) -> dict:
    return load_project_config(slug).get("vtube", {})


# ---------------------------------------------------------------------------
# vtube_launch_runtime
# ---------------------------------------------------------------------------

async def _vtube_launch_runtime(args: dict) -> str:
    slug    = args["project_slug"]
    cfg     = _vtube_cfg(slug)
    runtime = cfg.get("runtime", "")
    if not runtime:
        return json.dumps({"error": "runtime not configured"})
    if not shutil.which(runtime):
        return json.dumps({"error": f"Runtime '{runtime}' not found on PATH. "
                           "Install it or add it to PATH."})
    try:
        proc = await asyncio.create_subprocess_exec(
            runtime,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        return json.dumps({"launched": True, "runtime": runtime, "pid": proc.pid})
    except Exception as exc:
        log.exception("vtube_launch_runtime skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "vtube",
    name        = "vtube_launch_runtime",
    description = "Launch the configured VTube runtime (VTubeStudio, VSeeFace, VNyan, etc.).",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _vtube_launch_runtime,
)


# ---------------------------------------------------------------------------
# vtube_start_tracker
# ---------------------------------------------------------------------------

async def _vtube_start_tracker(args: dict) -> str:
    slug    = args["project_slug"]
    cfg     = _vtube_cfg(slug)
    tracker = cfg.get("tracker", "openSeeFace")

    if tracker == "openSeeFace":
        cmd = ["python", "facetracker.py", "-c", "0", "-v", "3", "--model", "3"]
        if not shutil.which("python"):
            return json.dumps({"error": "python not found on PATH"})
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )
            return json.dumps({"launched": True, "tracker": tracker, "pid": proc.pid})
        except Exception as exc:
            log.exception("vtube_start_tracker skill failed")
            return json.dumps({"error": str(exc)})
    else:
        instructions = {
            "arkit":         "Use the ARKit face tracking app on your iPhone/iPad and connect via WiFi.",
            "ifacialmocap":  "Open iFacialMocap on your iPhone and enter this machine's IP address.",
        }
        msg = instructions.get(tracker, f"Start '{tracker}' manually — no CLI launch available.")
        return json.dumps({"info": msg, "tracker": tracker})


registry.register(
    scope       = "vtube",
    name        = "vtube_start_tracker",
    description = "Start the face tracker. For openSeeFace: launches facetracker.py. For others: returns setup instructions.",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _vtube_start_tracker,
)
