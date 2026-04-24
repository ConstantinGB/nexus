from __future__ import annotations
import asyncio
from datetime import datetime, timedelta

from nexus.core.config_manager import (
    load_global_config, save_global_config,
    load_project_config, save_project_config,
)
from nexus.core.project_manager import list_projects
from nexus.core.logger import get

log = get("core.scheduler")

_INTERVALS: dict[str, timedelta] = {
    "daily":  timedelta(hours=24),
    "weekly": timedelta(days=7),
}
_POLL_SECONDS = 3600   # check every hour
_STARTUP_DELAY = 60    # wait before first check


def _is_due(last_run_iso: str | None, schedule: str) -> bool:
    if schedule not in _INTERVALS:
        return False
    if not last_run_iso:
        return True
    try:
        return datetime.now() - datetime.fromisoformat(last_run_iso) >= _INTERVALS[schedule]
    except ValueError:
        return True


class BackupScheduler:
    def __init__(self, app) -> None:
        self._app  = app
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())
        log.info("Backup scheduler started (poll=%ds)", _POLL_SECONDS)

    def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None
            log.info("Backup scheduler stopped")

    async def _loop(self) -> None:
        await asyncio.sleep(_STARTUP_DELAY)
        while True:
            try:
                await self._check_all()
            except Exception:
                log.exception("Scheduler check error")
            await asyncio.sleep(_POLL_SECONDS)

    async def _check_all(self) -> None:
        loop = asyncio.get_event_loop()

        # System-level backup
        cfg     = load_global_config()
        sys_bak = cfg.get("system_modules", {}).get("backup", {})
        if sys_bak.get("enabled") and _is_due(
            sys_bak.get("last_run"), sys_bak.get("schedule", "manual")
        ):
            await self._run_system_backup(loop, cfg, sys_bak)

        # Per-project backups
        for project in list_projects():
            if project.module != "backup":
                continue
            proj_cfg = load_project_config(project.slug)
            bak = proj_cfg.get("backup", {})
            if bak.get("configured") and _is_due(
                bak.get("last_run"), bak.get("schedule", "manual")
            ):
                await self._run_project_backup(loop, project, proj_cfg, bak)

    async def _run_system_backup(self, loop, cfg: dict, sys_bak: dict) -> None:
        from modules.backup.backup_ops import restic_ensure_initialized, restic_backup
        repo  = sys_bak.get("repo_path", "")
        pw    = sys_bak.get("password", "")
        paths = [p.strip() for p in sys_bak.get("paths", "").split(",") if p.strip()]
        if not repo or not paths:
            log.warning("Scheduled system backup skipped: repo or paths not configured")
            return

        log.info("Scheduled system backup starting")
        self._app.notify("Scheduled backup running…")
        ok, _ = await loop.run_in_executor(None, restic_ensure_initialized, repo, pw)
        if not ok:
            self._app.notify("Scheduled backup: init failed — see log.", severity="error")
            return
        ok, out = await loop.run_in_executor(None, restic_backup, repo, pw, paths)
        if ok:
            cfg["system_modules"]["backup"]["last_run"] = datetime.now().isoformat()
            save_global_config(cfg)
            self._app.notify("Scheduled backup complete.")
            log.info("Scheduled system backup complete")
        else:
            self._app.notify("Scheduled backup failed — see log.", severity="error")
            log.error("Scheduled system backup failed: %s", out)

    async def _run_project_backup(self, loop, project, proj_cfg: dict, bak: dict) -> None:
        from modules.backup.backup_ops import restic_ensure_initialized, restic_backup
        repo  = bak.get("repo", "")
        pw    = bak.get("password", "")
        paths = bak.get("paths", [])
        if not repo or not paths:
            log.warning("Scheduled backup skipped (%s): repo or paths not configured",
                        project.slug)
            return

        log.info("Scheduled backup starting: %s", project.slug)
        self._app.notify(f"Scheduled backup: {project.name}…")
        ok, _ = await loop.run_in_executor(None, restic_ensure_initialized, repo, pw)
        if not ok:
            self._app.notify(f"Backup init failed: {project.name}", severity="error")
            return
        ok, out = await loop.run_in_executor(None, restic_backup, repo, pw, paths)
        if ok:
            proj_cfg["backup"]["last_run"] = datetime.now().isoformat()
            save_project_config(project.slug, proj_cfg)
            self._app.notify(f"Backup complete: {project.name}")
            log.info("Scheduled backup complete: %s", project.slug)
        else:
            self._app.notify(f"Backup failed: {project.name} — see log.", severity="error")
            log.error("Scheduled backup failed %s: %s", project.slug, out)
