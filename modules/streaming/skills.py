from __future__ import annotations
import asyncio
import json
import shutil
from pathlib import Path

from nexus.ai.skill_registry import registry
from nexus.core.config_manager import load_project_config
from nexus.core.logger import get

log = get("skills.streaming")


def _streaming_cfg(slug: str) -> dict:
    return load_project_config(slug).get("streaming", {})


# ---------------------------------------------------------------------------
# streaming_list_scenes
# ---------------------------------------------------------------------------

async def _streaming_list_scenes(args: dict) -> str:
    slug = args["project_slug"]
    cfg  = _streaming_cfg(slug)
    raw  = cfg.get("obs_config_dir", "")
    if not raw:
        return json.dumps({"error": "obs_config_dir not configured"})
    scenes_dir = Path(raw).expanduser() / "basic" / "scenes"
    if not scenes_dir.exists():
        return json.dumps({"scenes": [], "note": "Scenes directory not found"})
    try:
        scenes = [f.name for f in sorted(scenes_dir.glob("*.json"))]
        return json.dumps({"scenes": scenes})
    except Exception as exc:
        log.exception("streaming_list_scenes skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "streaming",
    name        = "streaming_list_scenes",
    description = "List OBS scene collection JSON files from the OBS config directory.",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _streaming_list_scenes,
)


# ---------------------------------------------------------------------------
# streaming_launch_obs
# ---------------------------------------------------------------------------

async def _streaming_launch_obs(args: dict) -> str:
    slug = args["project_slug"]
    cfg  = _streaming_cfg(slug)
    bin_ = cfg.get("obs_bin", "obs")
    if not shutil.which(bin_):
        return json.dumps({"error": f"OBS binary '{bin_}' not found on PATH"})
    try:
        proc = await asyncio.create_subprocess_exec(
            bin_,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        return json.dumps({"launched": True, "pid": proc.pid})
    except Exception as exc:
        log.exception("streaming_launch_obs skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "streaming",
    name        = "streaming_launch_obs",
    description = "Launch OBS Studio.",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _streaming_launch_obs,
)


# ---------------------------------------------------------------------------
# streaming_check_logs
# ---------------------------------------------------------------------------

async def _streaming_check_logs(args: dict) -> str:
    slug = args["project_slug"]
    cfg  = _streaming_cfg(slug)
    raw  = cfg.get("obs_config_dir", "")
    if not raw:
        return json.dumps({"error": "obs_config_dir not configured"})
    logs_dir = Path(raw).expanduser() / "logs"
    if not logs_dir.exists():
        return json.dumps({"error": "OBS logs directory not found"})
    try:
        files = await asyncio.to_thread(lambda: sorted(
            logs_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True
        ))
        if not files:
            return json.dumps({"error": "No log files found"})
        lines = (await asyncio.to_thread(files[0].read_text, errors="replace")).splitlines()
        return json.dumps({"log_file": files[0].name, "lines": lines[-50:]})
    except Exception as exc:
        log.exception("streaming_check_logs skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "streaming",
    name        = "streaming_check_logs",
    description = "Return the last 50 lines from the most recent OBS log file.",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _streaming_check_logs,
)
