from __future__ import annotations
import asyncio
from pathlib import Path

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, Button, Log, Select, Input
from textual.containers import Vertical, Horizontal, ScrollableContainer

from nexus.core.logger import get
from nexus.ui.tui.base_project_screen import BaseProjectScreen, InputModal, _screen_css

from modules.backup.backup_ops import (
    restic_ensure_initialized, restic_backup,
    restic_snapshots, restic_snapshots_json, restic_check, restic_forget, restic_restore,
)

log = get("backup.project_screen")


class BackupSettingsModal(ModalScreen):
    BINDINGS = [("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    BackupSettingsModal { align: center middle; }
    #bs-dialog {
        background: #2D1B4E; border: solid #00B4FF;
        width: 82; height: 36;
    }
    #bs-title   { color: #00B4FF; text-style: bold; height: 2; padding: 0 2; }
    #bs-warning { color: #FF8800; height: 2; padding: 0 2; }
    #bs-scroll  { height: 1fr; border-bottom: solid #3A2260; }
    .bs-label   { color: #8888AA; height: 1; margin-top: 1; }
    BackupSettingsModal ScrollableContainer Input  { margin-bottom: 1; }
    BackupSettingsModal ScrollableContainer Select { margin-bottom: 1; }
    #bs-btns    { height: 3; padding: 0 2; }
    #bs-btns Button { margin-right: 1; }
    """

    def __init__(self, cfg: dict) -> None:
        super().__init__()
        self._cfg = cfg

    def compose(self) -> ComposeResult:
        m = self._cfg
        paths_str    = ", ".join(m.get("paths", []))
        excludes_str = ", ".join(m.get("excludes", []))
        schedule_val = m.get("schedule", "manual")
        if schedule_val not in ("manual", "daily", "weekly"):
            schedule_val = "manual"
        with Vertical(id="bs-dialog"):
            yield Label("Backup Settings", id="bs-title")
            yield Label("⚠  Changing the repository path requires re-initialisation.", id="bs-warning")
            with ScrollableContainer(id="bs-scroll"):
                yield Label("Repository path / SFTP target:", classes="bs-label")
                yield Input(m.get("repo", ""), id="bs-repo",
                            placeholder="/path/to/repo or sftp:user@host:/path")
                yield Label("Paths to back up (comma-separated):", classes="bs-label")
                yield Input(paths_str, id="bs-paths",
                            placeholder="~/projects, ~/documents")
                yield Label("Excludes (comma-separated glob patterns):", classes="bs-label")
                yield Input(excludes_str, id="bs-excludes",
                            placeholder="*.tmp, .git, node_modules")
                yield Label("Schedule:", classes="bs-label")
                yield Select(
                    [("Manual", "manual"), ("Daily", "daily"), ("Weekly", "weekly")],
                    value=schedule_val, id="bs-schedule", allow_blank=False,
                )
                yield Label("Keep daily snapshots:", classes="bs-label")
                yield Input(str(m.get("keep_daily", 7)),  id="bs-keep-daily",
                            placeholder="7", type="integer")
                yield Label("Keep weekly snapshots:", classes="bs-label")
                yield Input(str(m.get("keep_weekly", 4)), id="bs-keep-weekly",
                            placeholder="4", type="integer")
            with Horizontal(id="bs-btns"):
                yield Button("Save", id="bs-save", variant="primary")
                yield Button("Cancel", id="bs-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "bs-cancel":
            self.dismiss(None)
            return
        if event.button.id == "bs-save":
            try:
                keep_daily  = max(1, int(self.query_one("#bs-keep-daily",  Input).value or "7"))
                keep_weekly = max(1, int(self.query_one("#bs-keep-weekly", Input).value or "4"))
            except ValueError:
                keep_daily, keep_weekly = 7, 4
            paths_raw    = self.query_one("#bs-paths",    Input).value
            excludes_raw = self.query_one("#bs-excludes", Input).value
            result = {
                "repo":         self.query_one("#bs-repo", Input).value.strip(),
                "paths":        [p.strip() for p in paths_raw.split(",")    if p.strip()],
                "excludes":     [p.strip() for p in excludes_raw.split(",") if p.strip()],
                "schedule":     str(self.query_one("#bs-schedule", Select).value),
                "keep_daily":   keep_daily,
                "keep_weekly":  keep_weekly,
            }
            self.dismiss(result)

    def action_cancel(self) -> None:
        self.dismiss(None)


class SnapshotPickerModal(ModalScreen):
    DEFAULT_CSS = """
    SnapshotPickerModal { align: center middle; }
    #sp-dialog {
        background: #2D1B4E; border: solid #00B4FF;
        padding: 1 2; width: 72; height: auto;
    }
    #sp-title  { color: #00B4FF; text-style: bold; height: 2; }
    #sp-select { margin-bottom: 1; }
    #sp-btns   { height: 3; }
    #sp-btns Button { margin-right: 1; }
    """

    def __init__(self, snapshots: list[dict]) -> None:
        super().__init__()
        self._snapshots = snapshots

    def compose(self) -> ComposeResult:
        options = [
            (
                f"{s.get('time', '')[:16].replace('T', ' ')}  "
                f"{s.get('id', '')[:8]}  "
                f"{s.get('hostname', '')}",
                s["id"],
            )
            for s in self._snapshots
        ]
        with Vertical(id="sp-dialog"):
            yield Label("Select a snapshot to restore:", id="sp-title")
            yield Select(options, id="sp-select", allow_blank=False)
            with Horizontal(id="sp-btns"):
                yield Button("Restore →", id="sp-ok", variant="primary")
                yield Button("Cancel",    id="sp-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "sp-ok":
            val = self.query_one("#sp-select", Select).value
            self.dismiss(val if val is not Select.BLANK else None)
        else:
            self.dismiss(None)


class ProjectScreen(BaseProjectScreen):
    MODULE_KEY        = "backup"
    MODULE_LABEL      = "BACKUP"
    REQUIRED_BINARIES = [("restic", "restic")]
    SETUP_FIELDS      = [
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
            Button("Settings…",      id="btn-settings"),
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

        keep_daily  = self._mod.get("keep_daily",  7)
        keep_weekly = self._mod.get("keep_weekly", 4)
        excludes    = self._mod.get("excludes",    [])

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
                Label("Retention:", classes="info-key"),
                Label(f"daily={keep_daily}  weekly={keep_weekly}", classes="info-val"),
                classes="info-row",
            ),
            Horizontal(
                Label("Excludes:", classes="info-key"),
                Label(", ".join(excludes) if excludes else "(none)", classes="info-val"),
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
            if getattr(self, "_backup_running", False):
                self.app.notify("Backup already in progress.", severity="warning")
                return
            self.run_worker(self._do_backup())
        elif bid == "btn-snapshots":
            self.run_worker(self._do_snapshots())
        elif bid == "btn-check":
            self.run_worker(self._do_check())
        elif bid == "btn-forget":
            self.run_worker(self._do_forget())
        elif bid == "btn-restore":
            self.run_worker(self._pick_and_restore())
        elif bid == "btn-settings":
            self._open_settings()

    # ── Settings ──────────────────────────────────────────────────────────────

    def _open_settings(self) -> None:
        self.app.push_screen(
            BackupSettingsModal(dict(self._mod)),
            self._on_settings_saved,
        )

    def _on_settings_saved(self, result: dict | None) -> None:
        if not result:
            return
        from nexus.core.config_manager import load_project_config, save_project_config
        cfg = load_project_config(self.project.slug)
        cfg.setdefault("backup", {}).update(result)
        save_project_config(self.project.slug, cfg)
        self._mod = cfg["backup"]
        self.run_worker(self._populate_content())
        self.app.notify("Backup settings saved.", severity="information")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _append_log(self, text: str) -> None:
        self.query_one("#output-log", Log).write_line(text)

    # ── Workers ───────────────────────────────────────────────────────────────

    def _repo_and_password(self) -> tuple[str, str]:
        repo = self._mod.get("repo", "")
        pw   = self._mod.get("password", "")
        return repo, pw

    async def _do_backup(self) -> None:
        self._backup_running = True
        try:
            await self._do_backup_inner()
        finally:
            self._backup_running = False

    async def _do_backup_inner(self) -> None:
        repo, pw = self._repo_and_password()
        paths    = self._mod.get("paths", [])
        excludes = self._mod.get("excludes", [])
        if not repo:
            self._append_log("No repository configured.")
            return
        self._append_log("Initialising repository if needed…")
        loop = asyncio.get_running_loop()
        ok, msg = await loop.run_in_executor(
            None, restic_ensure_initialized, repo, pw
        )
        if not ok:
            self._append_log(f"Init failed: {msg}")
            self.app.notify("Repository init failed — see log.", severity="error")
            return
        self._append_log("Running backup…")
        ok, out = await loop.run_in_executor(
            None, restic_backup, repo, pw, paths, excludes
        )
        self._append_log(out)
        if ok:
            self.app.notify("Backup complete.", severity="information")
        else:
            self.app.notify("Backup failed — see log.", severity="error")

    async def _do_snapshots(self) -> None:
        repo, pw = self._repo_and_password()
        self._append_log("Fetching snapshots…")
        ok, out = await asyncio.get_running_loop().run_in_executor(
            None, restic_snapshots, repo, pw
        )
        self._append_log(out if out else "(no snapshots)")

    async def _do_check(self) -> None:
        repo, pw = self._repo_and_password()
        self._append_log("Checking repository integrity…")
        ok, out = await asyncio.get_running_loop().run_in_executor(
            None, restic_check, repo, pw
        )
        self._append_log(out)
        if ok:
            self.app.notify("Repository OK.", severity="information")
        else:
            self.app.notify("Integrity check failed — see log.", severity="error")

    async def _do_forget(self) -> None:
        repo, pw    = self._repo_and_password()
        keep_daily  = int(self._mod.get("keep_daily",  7))
        keep_weekly = int(self._mod.get("keep_weekly", 4))
        self._append_log(
            f"Forgetting old snapshots (keep-daily={keep_daily}, "
            f"keep-weekly={keep_weekly}) + pruning…"
        )
        ok, out = await asyncio.get_running_loop().run_in_executor(
            None, restic_forget, repo, pw, keep_daily, keep_weekly
        )
        self._append_log(out)
        if ok:
            self.app.notify("Forget + prune complete.", severity="information")
        else:
            self.app.notify("Forget/prune failed — see log.", severity="error")

    async def _do_restore(self, snap_id: str, target: str) -> None:
        from pathlib import Path as _Path
        import os as _os
        target_path = _Path(target).expanduser().resolve()
        home = _Path(_os.path.expanduser("~")).resolve()
        if not (str(target_path).startswith(str(home) + _os.sep) or target_path == home):
            self._append_log(
                f"Restore refused: target '{target}' is outside your home directory."
            )
            self.app.notify("Restore target must be inside your home directory.", severity="error")
            return
        repo, pw = self._repo_and_password()
        self._append_log(f"Restoring snapshot {snap_id} → {target}…")
        ok, out = await asyncio.get_running_loop().run_in_executor(
            None, restic_restore, repo, pw, snap_id, target
        )
        self._append_log(out)
        if ok:
            self.app.notify(f"Restored to {target}.", severity="information")
        else:
            self.app.notify("Restore failed — see log.", severity="error")

    async def _pick_and_restore(self) -> None:
        repo, pw = self._repo_and_password()
        if not repo:
            self._append_log("No repository configured.")
            return
        self._append_log("Fetching snapshot list…")
        ok, snapshots = await asyncio.get_running_loop().run_in_executor(
            None, restic_snapshots_json, repo, pw
        )
        if not ok or not snapshots:
            self._append_log("No snapshots found — run a backup first.")
            self.app.notify("No snapshots available.", severity="warning")
            return

        def _on_snap_picked(snap_id: str | None) -> None:
            if not snap_id:
                return
            self.app.push_screen(
                InputModal("Restore Target", "Restore to directory:", "/tmp/restore"),
                lambda target: self._on_target_picked(snap_id, target),
            )

        def _on_target_picked(snap_id: str, target: str | None) -> None:
            if not target:
                return
            self.run_worker(self._do_restore(snap_id, target))

        self.app.push_screen(SnapshotPickerModal(snapshots), _on_snap_picked)
