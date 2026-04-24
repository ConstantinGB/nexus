from __future__ import annotations
import asyncio
import json

from nexus.ai.skill_registry import registry
from nexus.core.config_manager import load_project_config
from nexus.core.logger import get

log = get("skills.backup")


def _backup_cfg(slug: str) -> dict:
    return load_project_config(slug).get("backup", {})


# ---------------------------------------------------------------------------
# backup_run_backup
# ---------------------------------------------------------------------------

async def _backup_run_backup(args: dict) -> str:
    slug = args["project_slug"]
    cfg  = _backup_cfg(slug)
    repo = cfg.get("repo", "")
    pw   = cfg.get("password", "")
    paths = cfg.get("paths", [])
    if not repo:
        return json.dumps({"error": "No repository configured for this backup project."})
    if not paths:
        return json.dumps({"error": "No paths configured to back up."})

    import os
    env = os.environ.copy()
    env["RESTIC_PASSWORD"] = pw
    try:
        proc = await asyncio.create_subprocess_exec(
            "restic", "-r", repo, "backup", *paths,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )
        out, _ = await proc.communicate()
        output = out.decode(errors="replace").strip()
        return json.dumps({"success": proc.returncode == 0, "output": output})
    except FileNotFoundError:
        return json.dumps({"error": "restic not found — install it via Settings → Setup."})
    except Exception as exc:
        log.exception("backup_run_backup failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "backup",
    name        = "backup_run_backup",
    description = "Trigger a restic backup for the specified Nexus backup project.",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _backup_run_backup,
)


# ---------------------------------------------------------------------------
# backup_list_snapshots
# ---------------------------------------------------------------------------

async def _backup_list_snapshots(args: dict) -> str:
    slug = args["project_slug"]
    cfg  = _backup_cfg(slug)
    repo = cfg.get("repo", "")
    pw   = cfg.get("password", "")
    if not repo:
        return json.dumps({"error": "No repository configured."})

    import os
    env = os.environ.copy()
    env["RESTIC_PASSWORD"] = pw
    try:
        proc = await asyncio.create_subprocess_exec(
            "restic", "-r", repo, "snapshots", "--compact",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )
        out, _ = await proc.communicate()
        output = out.decode(errors="replace").strip()
        return json.dumps({"success": proc.returncode == 0, "output": output})
    except FileNotFoundError:
        return json.dumps({"error": "restic not found."})
    except Exception as exc:
        log.exception("backup_list_snapshots failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "backup",
    name        = "backup_list_snapshots",
    description = "List all restic snapshots for the specified Nexus backup project.",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _backup_list_snapshots,
)


# ---------------------------------------------------------------------------
# backup_check
# ---------------------------------------------------------------------------

async def _backup_check(args: dict) -> str:
    slug = args["project_slug"]
    cfg  = _backup_cfg(slug)
    repo = cfg.get("repo", "")
    pw   = cfg.get("password", "")
    if not repo:
        return json.dumps({"error": "No repository configured."})

    import os
    env = os.environ.copy()
    env["RESTIC_PASSWORD"] = pw
    try:
        proc = await asyncio.create_subprocess_exec(
            "restic", "-r", repo, "check",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )
        out, _ = await proc.communicate()
        output = out.decode(errors="replace").strip()
        ok = proc.returncode == 0
        return json.dumps({
            "success": ok,
            "output":  output,
            "status":  "OK" if ok else "integrity errors detected",
        })
    except FileNotFoundError:
        return json.dumps({"error": "restic not found."})
    except Exception as exc:
        log.exception("backup_check failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "backup",
    name        = "backup_check",
    description = "Run a restic integrity check on the backup repository.",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _backup_check,
)
