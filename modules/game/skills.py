from __future__ import annotations
import asyncio
import json
import shutil
from pathlib import Path

from nexus.ai.skill_registry import registry
from nexus.core.config_manager import load_project_config
from nexus.core.logger import get

log = get("skills.game")


def _game_cfg(slug: str) -> dict:
    return load_project_config(slug).get("game", {})


# ---------------------------------------------------------------------------
# game_scene_list
# ---------------------------------------------------------------------------

async def _game_scene_list(args: dict) -> str:
    slug = args["project_slug"]
    cfg  = _game_cfg(slug)
    raw  = cfg.get("project_path", "")
    if not raw:
        return json.dumps({"error": "project_path not configured"})
    path = Path(raw).expanduser()
    try:
        scenes = [str(p.relative_to(path)) for p in path.rglob("*.tscn")]
        return json.dumps({"scenes": scenes, "count": len(scenes)})
    except Exception as exc:
        log.exception("game_scene_list skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "game",
    name        = "game_scene_list",
    description = "List all Godot scene files (.tscn) in the project directory.",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _game_scene_list,
)


# ---------------------------------------------------------------------------
# game_launch_editor
# ---------------------------------------------------------------------------

async def _game_launch_editor(args: dict) -> str:
    slug = args["project_slug"]
    cfg  = _game_cfg(slug)
    raw  = cfg.get("project_path", "")
    bin_ = cfg.get("godot_bin", "godot4")
    if not raw:
        return json.dumps({"error": "project_path not configured"})
    if not shutil.which(bin_):
        return json.dumps({"error": f"Godot binary '{bin_}' not found on PATH"})
    path = Path(raw).expanduser()
    try:
        proc = await asyncio.create_subprocess_exec(
            bin_, "--editor", "--path", str(path),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        return json.dumps({"launched": True, "pid": proc.pid})
    except Exception as exc:
        log.exception("game_launch_editor skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "game",
    name        = "game_launch_editor",
    description = "Launch the Godot editor for the configured game project.",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _game_launch_editor,
)


# ---------------------------------------------------------------------------
# game_run
# ---------------------------------------------------------------------------

async def _game_run(args: dict) -> str:
    slug = args["project_slug"]
    cfg  = _game_cfg(slug)
    raw  = cfg.get("project_path", "")
    bin_ = cfg.get("godot_bin", "godot4")
    if not raw:
        return json.dumps({"error": "project_path not configured"})
    if not shutil.which(bin_):
        return json.dumps({"error": f"Godot binary '{bin_}' not found on PATH"})
    path = Path(raw).expanduser()
    try:
        proc = await asyncio.create_subprocess_exec(
            bin_, "--path", str(path),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        return json.dumps({"launched": True, "pid": proc.pid})
    except Exception as exc:
        log.exception("game_run skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "game",
    name        = "game_run",
    description = "Run the Godot game project.",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _game_run,
)
