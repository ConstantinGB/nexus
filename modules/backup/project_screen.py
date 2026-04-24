from __future__ import annotations
import asyncio
from pathlib import Path

from textual.widgets import Label, Button, Log
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.ui.base_project_screen import BaseProjectScreen, InputModal, _screen_css

from modules.backup.backup_ops import (
    restic_ensure_initialized, restic_backup,
    restic_snapshots, restic_check, restic_forget, restic_restore,
)

log = get("backup.project_screen")


class BackupProjectScreen(BaseProjectScreen):
    MODULE_KEY   = "backup"
    MODULE_LABEL = "BACKUP"
    SETUP_FIELDS = [
        {"id": "repo",     "label": "Repository path / SFTP target",
         "placeholder": "/home/user/nexus-backup or sftp:user@host:/path"},
        {"id": "paths",    "label": "Paths to back up (comma-separated)",
         "placeholder": "~/nexus/projects, ~/nexus/config"},
    ]

    DEFAULT_CSS = _screen_css("BackupProjectScreen") + """
    .snap-row  { height: 1; }
    .snap-id   { color: #00B4FF; width: 14; }
    .snap-date { color: #8080AA; width: 24; }
    .snap-host { color: #E0E0FF; width: 1fr; }
    """

    # ── Action buttons ────────────────────────────────────────────────────────

    def _compose_action_buttons(self) -> list:
        return [
            Button("Run Backup",     id="btn-backup",    variant="primary"),
            Button("List Snapshots", id="btn-snapshots"),
            Button("Check",          id="btn-check"),
            Button("Forget + Prune", id="btn-forget"),
            Button("Restore…",       id="btn-restore"),
        ]

    # ── Main content ──────────────────────────────────────────────────────────

    async def _populate_content(self) -> None:
        area = self.query_one("#content-area", Vertical)
        await area.remove_children()

        repo    = self._mod.get("repo", "")
        paths   = self._mod.get("paths", [])
        backend = self._mod.get("backend", "local")
        sched   = self._mod.get("schedule", "manual")

        last_run_raw = self._mod.get("last_run")
        last_run_display = (
            last_run_raw[:16].replace("T", " ") if last_run_raw else "Never"
        )

        widgets = [
            Horizontal(
                Label("Backend:",  classes="info-key"),
                Label(backend,     classes="info-val"),
                classes="info-row",
            ),
            Horizontal(
                Label("Repository:", classes="info-key"),
                Label(repo or "(not set)", classes="info-val"),
                classes="info-row",
            ),
            Horizontal(
                Label("Schedule:",  classes="info-key"),
                Label(sched,        classes="info-val"),
                classes="info-row",
            ),
            Horizontal(
                Label("Paths:",     classes="info-key"),
                Label(", ".join(paths) if paths else "(none)",
                      classes="info-val"),
                classes="info-row",
            ),
            Horizontal(
                Label("Last backup:", classes="info-key"),
                Label(last_run_display, classes="info-val"),
                classes="info-row",
            ),
        ]
        for w in widgets:
            await area.mount(w)

    # ── Action handler ────────────────────────────────────────────────────────

    def _handle_action(self, bid: str) -> None:
        if bid == "btn-backup":
            self.run_worker(self._do_backup())
        elif bid == "btn-snapshots":
            self.run_worker(self._do_snapshots())
        elif bid == "btn-check":
            self.run_worker(self._do_check())
        elif bid == "btn-forget":
            self.run_worker(self._do_forget())
        elif bid == "btn-restore":
            self.app.push_screen(
                InputModal("Restore",
                           "Enter snapshot ID (or 'latest') and target path: "
                           "snapshotID:/target/path",
                           placeholder="latest:/tmp/restore"),
                self._on_restore_input,
            )

    def _on_restore_input(self, value: str | None) -> None:
        if not value:
            return
        parts = value.split(":", 1)
        if len(parts) != 2:
            self.app.notify("Format: snapshotID:/target/path", severity="warning")
            return
        snap_id, target = parts
        self.run_worker(self._do_restore(snap_id.strip(), target.strip()))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _append_log(self, text: str) -> None:
        self.query_one("#output-log", Log).write_line(text)

    # ── Workers ───────────────────────────────────────────────────────────────

    def _repo_and_password(self) -> tuple[str, str]:
        repo = self._mod.get("repo", "")
        pw   = self._mod.get("password", "")
        return repo, pw

    async def _do_backup(self) -> None:
        repo, pw = self._repo_and_password()
        paths = self._mod.get("paths", [])
        if not repo:
            self._append_log("No repository configured.")
            return
        self._append_log("Initialising repository if needed…")
        loop = asyncio.get_event_loop()
        ok, msg = await loop.run_in_executor(
            None, restic_ensure_initialized, repo, pw
        )
        if not ok:
            self._append_log(f"Init failed: {msg}")
            self.app.notify("Repository init failed — see log.", severity="error")
            return
        self._append_log("Running backup…")
        ok, out = await loop.run_in_executor(
            None, restic_backup, repo, pw, paths
        )
        self._append_log(out)
        if ok:
            self.app.notify("Backup complete.", severity="information")
        else:
            self.app.notify("Backup failed — see log.", severity="error")

    async def _do_snapshots(self) -> None:
        repo, pw = self._repo_and_password()
        self._append_log("Fetching snapshots…")
        ok, out = await asyncio.get_event_loop().run_in_executor(
            None, restic_snapshots, repo, pw
        )
        self._append_log(out if out else "(no snapshots)")

    async def _do_check(self) -> None:
        repo, pw = self._repo_and_password()
        self._append_log("Checking repository integrity…")
        ok, out = await asyncio.get_event_loop().run_in_executor(
            None, restic_check, repo, pw
        )
        self._append_log(out)
        if ok:
            self.app.notify("Repository OK.", severity="information")
        else:
            self.app.notify("Integrity check failed — see log.", severity="error")

    async def _do_forget(self) -> None:
        repo, pw = self._repo_and_password()
        self._append_log("Forgetting old snapshots (keep-daily=7, keep-weekly=4) + pruning…")
        ok, out = await asyncio.get_event_loop().run_in_executor(
            None, restic_forget, repo, pw, 7, 4
        )
        self._append_log(out)
        if ok:
            self.app.notify("Forget + prune complete.", severity="information")
        else:
            self.app.notify("Forget/prune failed — see log.", severity="error")

    async def _do_restore(self, snap_id: str, target: str) -> None:
        repo, pw = self._repo_and_password()
        self._append_log(f"Restoring snapshot {snap_id} → {target}…")
        ok, out = await asyncio.get_event_loop().run_in_executor(
            None, restic_restore, repo, pw, snap_id, target
        )
        self._append_log(out)
        if ok:
            self.app.notify(f"Restored to {target}.", severity="information")
        else:
            self.app.notify("Restore failed — see log.", severity="error")
