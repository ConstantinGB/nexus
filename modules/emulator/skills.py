from __future__ import annotations
import asyncio
import json
import shutil
from pathlib import Path

from nexus.ai.skill_registry import registry, require_project
from nexus.core.logger import get

log = get("skills.emulator")


def _emu_cfg(slug: str) -> dict:
    return require_project(slug).get("emulator", {})


# ---------------------------------------------------------------------------
# emulator_list_systems
# ---------------------------------------------------------------------------

async def _emulator_list_systems(args: dict) -> str:
    slug = args["project_slug"]
    cfg  = _emu_cfg(slug)
    raw  = cfg.get("rom_dir", "")
    if not raw:
        return json.dumps({"error": "rom_dir not configured"})
    rom_dir = Path(raw).expanduser()
    if not rom_dir.exists():
        return json.dumps({"systems": [], "note": "ROM directory not found"})
    try:
        systems = []
        for d in sorted(rom_dir.iterdir()):
            if d.is_dir():
                count = sum(1 for _ in d.iterdir() if _.is_file())
                systems.append({"system": d.name, "rom_count": count})
        return json.dumps({"systems": systems})
    except Exception as exc:
        log.exception("emulator_list_systems skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "emulator",
    name        = "emulator_list_systems",
    description = "List ROM directories under the configured rom_dir, with the file count per system.",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _emulator_list_systems,
)


# ---------------------------------------------------------------------------
# emulator_launch
# ---------------------------------------------------------------------------

async def _emulator_launch(args: dict) -> str:
    slug   = args["project_slug"]
    system = args["system"]
    rom    = args.get("rom", "")
    cfg    = _emu_cfg(slug)
    raw    = cfg.get("rom_dir", "")
    bin_   = cfg.get("retroarch_bin", "retroarch")
    if not raw:
        return json.dumps({"error": "rom_dir not configured"})
    if not shutil.which(bin_):
        return json.dumps({"error": f"RetroArch binary '{bin_}' not found on PATH"})
    content_dir = Path(raw).expanduser() / system
    cmd = [bin_]
    if rom:
        cmd += [str(content_dir / rom)]
    else:
        cmd += ["--contentdir", str(content_dir)]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        return json.dumps({"launched": True, "pid": proc.pid, "system": system, "rom": rom})
    except Exception as exc:
        log.exception("emulator_launch skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "emulator",
    name        = "emulator_launch",
    description = "Launch RetroArch for a given system. Optionally specify a ROM filename within that system's directory.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "system":       {"type": "string", "description": "System subdirectory name (e.g. 'SNES', 'GBA')"},
            "rom":          {"type": "string", "description": "ROM filename within the system directory (optional)"},
        },
        "required": ["project_slug", "system"],
    },
    handler = _emulator_launch,
)
