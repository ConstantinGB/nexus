from __future__ import annotations
import asyncio

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Label, Input, Button, Log, Select
from textual.containers import Vertical, Horizontal, ScrollableContainer

from nexus.core.logger import get
from nexus.core.project_manager import ProjectInfo
from nexus.core.config_manager import save_project_config

from modules.backup.backup_ops import restic_init

log = get("backup.setup_screen")

_ALL_STEPS = ["step-backend", "step-paths", "step-password", "step-init", "step-done"]


class BackupSetupScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    DEFAULT_CSS = """
    BackupSetupScreen { background: #1A0A2E; }
    BackupSetupScreen Header { background: #2D1B4E; color: #00B4FF; }
    BackupSetupScreen Footer { background: #2D1B4E; color: #00FF88; }

    .step { padding: 1 2; }
    .step-title { color: #00B4FF; text-style: bold; margin-bottom: 1; }
    .field-label { color: #00FF88; height: 1; margin-top: 1; }
    .hint { color: #555588; height: 1; }
    #schedule-bar { height: 3; margin-bottom: 1; }
    #schedule-bar Select { width: 1fr; }
    .backend-btn {
        width: 16; margin-right: 1;
        background: #2D1B4E; color: #8080AA; border: solid #3A2260;
    }
    .backend-btn.selected { background: #1A1040; color: #00B4FF; border: solid #00B4FF; }
    #backend-bar { height: 3; margin-bottom: 1; }
    #btn-bar { height: 3; margin-top: 1; }
    #btn-bar Button { margin-right: 1; }
    #init-log { height: 12; border: solid #3A2260; background: #130822; }
    """

    def __init__(self, project: ProjectInfo) -> None:
        super().__init__()
        self._project = project
        self._backend  = "local"
        self._repo     = ""
        self._paths    = ""
        self._password = ""
        self._schedule = "manual"

    def compose(self) -> ComposeResult:
        yield Header()
        with ScrollableContainer():
            # ── Step 1: backend ───────────────────────────────────────────
            with Vertical(id="step-backend", classes="step"):
                yield Label("Backup Setup — Step 1: Choose backend",
                            classes="step-title")
                yield Label("Where should the backup repository live?",
                            classes="hint")
                with Horizontal(id="backend-bar"):
                    yield Button("Local path", id="btn-be-local",
                                 classes="backend-btn selected")
                    yield Button("NAS (SFTP)",  id="btn-be-sftp",
                                 classes="backend-btn")
                    yield Button("NFS mount",   id="btn-be-nfs",
                                 classes="backend-btn")

                yield Label("Repository path / SFTP target:", classes="field-label")
                yield Label(
                    "Local: /path/to/repo   SFTP: sftp:user@host:/path",
                    classes="hint",
                )
                yield Input(placeholder="/home/user/nexus-backup", id="input-repo")
                with Horizontal(id="btn-bar"):
                    yield Button("Next →", id="btn-next-1", variant="primary")

            # ── Step 2: backup targets ────────────────────────────────────
            with Vertical(id="step-paths", classes="step"):
                yield Label("Backup Setup — Step 2: What to back up",
                            classes="step-title")
                yield Label("Comma-separated list of paths to include.",
                            classes="hint")
                yield Input(
                    placeholder="~/nexus/projects, ~/nexus/config, ~/documents",
                    id="input-paths",
                )
                yield Label("Schedule:", classes="field-label")
                with Horizontal(id="schedule-bar"):
                    yield Select(
                        [("Manual", "manual"),
                         ("Daily",  "daily"),
                         ("Weekly", "weekly")],
                        value="manual",
                        id="input-schedule",
                        allow_blank=False,
                    )
                with Horizontal(id="btn-bar"):
                    yield Button("← Back",   id="btn-back-2")
                    yield Button("Next →",   id="btn-next-2", variant="primary")

            # ── Step 3: password ──────────────────────────────────────────
            with Vertical(id="step-password", classes="step"):
                yield Label("Backup Setup — Step 3: Repository password",
                            classes="step-title")
                yield Label(
                    "restic encrypts all backups. Choose a strong password "
                    "and store it somewhere safe — it cannot be recovered.",
                    classes="hint",
                )
                yield Input(
                    placeholder="strong-passphrase",
                    password=True,
                    id="input-password",
                )
                yield Label("Confirm password:", classes="field-label")
                yield Input(
                    placeholder="strong-passphrase",
                    password=True,
                    id="input-password-confirm",
                )
                with Horizontal(id="btn-bar"):
                    yield Button("← Back",        id="btn-back-3")
                    yield Button("Initialise →",  id="btn-next-3", variant="primary")

            # ── Step 4: initialise ────────────────────────────────────────
            with Vertical(id="step-init", classes="step"):
                yield Label("Backup Setup — Step 4: Initialising repository…",
                            classes="step-title")
                yield Log(id="init-log", highlight=True)
                with Horizontal(id="btn-bar"):
                    yield Button("← Back", id="btn-back-4")

            # ── Step 5: done ──────────────────────────────────────────────
            with Vertical(id="step-done", classes="step"):
                yield Label("Backup Setup — Complete!", classes="step-title")
                yield Label(
                    "Repository initialised. You can now run backups from the "
                    "project screen.",
                    classes="hint",
                )
                with Horizontal(id="btn-bar"):
                    yield Button("Open Project", id="btn-open", variant="primary")

        yield Footer()

    def on_mount(self) -> None:
        self.call_after_refresh(self._show_step, "step-backend")

    def _show_step(self, step_id: str) -> None:
        for sid in _ALL_STEPS:
            try:
                self.query_one(f"#{sid}").display = (sid == step_id)
            except Exception:
                pass

    def _select_backend(self, backend: str) -> None:
        self._backend = backend
        for be, btn_id in [("local", "btn-be-local"),
                           ("sftp",  "btn-be-sftp"),
                           ("nfs",   "btn-be-nfs")]:
            try:
                btn = self.query_one(f"#{btn_id}", Button)
                if be == backend:
                    btn.add_class("selected")
                else:
                    btn.remove_class("selected")
            except Exception:
                pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id

        # Backend selector
        if bid == "btn-be-local":
            self._select_backend("local")
            return
        if bid == "btn-be-sftp":
            self._select_backend("sftp")
            return
        if bid == "btn-be-nfs":
            self._select_backend("nfs")
            return

        if bid == "btn-next-1":
            repo = self.query_one("#input-repo", Input).value.strip()
            if not repo:
                self.app.notify("Enter a repository path.", severity="warning")
                return
            self._repo = repo
            self.call_after_refresh(self._show_step, "step-paths")

        elif bid == "btn-back-2":
            self.call_after_refresh(self._show_step, "step-backend")

        elif bid == "btn-next-2":
            paths = self.query_one("#input-paths", Input).value.strip()
            if not paths:
                self.app.notify("Enter at least one path.", severity="warning")
                return
            self._paths    = paths
            self._schedule = str(self.query_one("#input-schedule", Select).value)
            self.call_after_refresh(self._show_step, "step-password")

        elif bid == "btn-back-3":
            self.call_after_refresh(self._show_step, "step-paths")

        elif bid == "btn-next-3":
            pw  = self.query_one("#input-password",         Input).value
            pw2 = self.query_one("#input-password-confirm", Input).value
            if not pw:
                self.app.notify("Enter a password.", severity="warning")
                return
            if pw != pw2:
                self.app.notify("Passwords do not match.", severity="error")
                return
            self._password = pw
            self.call_after_refresh(self._show_step, "step-init")
            self.run_worker(self._do_init())

        elif bid == "btn-back-4":
            self.call_after_refresh(self._show_step, "step-password")

        elif bid == "btn-open":
            self.dismiss()

    async def _do_init(self) -> None:
        output_log = self.query_one("#init-log", Log)
        output_log.write_line(f"Initialising repository: {self._repo}")
        output_log.write_line("Running: restic init …")

        ok, out = await asyncio.get_event_loop().run_in_executor(
            None, restic_init, self._repo, self._password
        )
        for line in out.splitlines():
            output_log.write_line(line)

        if ok:
            output_log.write_line("\n✓ Repository initialised.")
            self._save_config()
            self.call_after_refresh(self._show_step, "step-done")
        else:
            output_log.write_line("\n✗ Initialisation failed — check output above.")
            self.app.notify("Initialisation failed.", severity="error")
            try:
                self.query_one("#btn-back-4", Button).disabled = False
            except Exception:
                pass

    def _save_config(self) -> None:
        # Password stored in local-only config.yaml (git-ignored, never uploaded).
        cfg = {
            "backup": {
                "setup_done":  True,
                "configured":  True,
                "backend":     self._backend,
                "repo":        self._repo,
                "password":    self._password,
                "paths":       [p.strip() for p in self._paths.split(",")
                                if p.strip()],
                "schedule":    self._schedule,
            }
        }
        save_project_config(self._project.slug, cfg)
        log.info("Backup project config saved for %s", self._project.slug)
