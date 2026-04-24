from __future__ import annotations
import asyncio
from pathlib import Path
from datetime import datetime, timezone

import yaml
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Header, Footer, Label, Input, Button,
    Select, Checkbox, Log,
)
from textual.containers import Vertical, Horizontal, ScrollableContainer

from nexus.core.logger import get
from nexus.core.project_manager import ProjectInfo

log = get("git.setup_screen")

_PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"

_ALL_STEPS = [
    "step-name", "step-type",
    "step-creds-github", "step-creds-selfhosted", "step-creds-local",
    "step-gitconfig", "step-software", "step-repos",
    "step-clone", "step-done",
]

_STEP_LABELS = {
    "step-name":            "Step 1 of 6 — Name",
    "step-type":            "Step 2 of 6 — Repository type",
    "step-creds-github":    "Step 3 of 6 — GitHub credentials",
    "step-creds-selfhosted":"Step 3 of 6 — Server credentials",
    "step-creds-local":     "Step 3 of 6 — Local path",
    "step-gitconfig":       "Step 4 of 6 — Git identity",
    "step-software":        "Step 5 of 6 — Software check",
    "step-repos":           "Step 6 of 6 — Select repositories",
    "step-clone":           "Cloning repositories…",
    "step-done":            "Setup complete",
}


class RepoCheckRow(Horizontal):
    DEFAULT_CSS = """
    RepoCheckRow { height: 3; padding: 0 1; }
    RepoCheckRow:hover { background: #3A2260; }
    RepoCheckRow .repo-name { color: #E0E0FF; width: 36; }
    RepoCheckRow .repo-vis  { color: #666699; width: 10; }
    RepoCheckRow .repo-desc { color: #8080AA; width: 1fr; }
    """

    def __init__(self, repo: dict, **kwargs):
        super().__init__(**kwargs)
        self.repo = repo

    def compose(self) -> ComposeResult:
        vis = "private" if self.repo.get("private") else "public"
        yield Checkbox("", id=f"cb_{self.repo['name']}")
        yield Label(self.repo["name"],                          classes="repo-name")
        yield Label(vis,                                        classes="repo-vis")
        yield Label((self.repo.get("description") or "")[:50], classes="repo-desc")


class GitSetupScreen(Screen):
    BINDINGS = [("escape", "dismiss", "Cancel")]

    DEFAULT_CSS = """
    GitSetupScreen { background: #1A0A2E; align: center middle; }
    GitSetupScreen Header { background: #2D1B4E; color: #00B4FF; }
    GitSetupScreen Footer { background: #2D1B4E; color: #00FF88; }

    #dialog {
        background: #2D1B4E;
        border: solid #00B4FF;
        padding: 1 2;
        width: 80;
        height: auto;
        max-height: 44;
    }
    #dialog-title { color: #00B4FF; text-style: bold; height: 2; }
    #step-label   { color: #666699; height: 1; margin-bottom: 1; }

    .field-label  { color: #00FF88; height: 1; margin-top: 1; }
    .hint         { color: #555588; height: 2; }
    .error-label  { color: #FF4444; height: 1; }
    .ok-label     { color: #00FF88; }
    Input         { margin-bottom: 0; }

    #repo-list    { height: 14; background: #1A0A2E; border: solid #3A2260; }
    #software-log { height: 8;  background: #0A0518; border: solid #3A2260; }
    #clone-log    { height: 12; background: #0A0518; border: solid #3A2260; }

    #btn-row      { height: 3; margin-top: 2; }
    #btn-back     { margin-right: 1; }
    """

    def __init__(self, project: ProjectInfo):
        super().__init__()
        self.project     = project
        self._git_type   = "github"
        self._repos: list[dict] = []
        self._token      = ""
        self._step       = "step-name"

    # ── Compose ──────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="dialog"):
            yield Label("Git Module Setup", id="dialog-title")
            yield Label("Step 1 of 6 — Name", id="step-label")

            # Step 1: Name
            with Vertical(id="step-name"):
                yield Label("Module name:", classes="field-label")
                yield Input(self.project.name, id="input-name")
                yield Label("This is what appears on your tile.", classes="hint")

            # Step 2: Git type
            with Vertical(id="step-type"):
                yield Label("Where are your repositories?", classes="field-label")
                yield Select(
                    [("GitHub", "github"),
                     ("Self-Hosted  (GitLab / Gitea / etc.)", "selfhosted"),
                     ("Local  (repos already on this machine)", "local")],
                    value="github",
                    id="select-type",
                )

            # Step 3a: GitHub credentials
            with Vertical(id="step-creds-github"):
                yield Label("Personal Access Token (PAT):", classes="field-label")
                yield Input(placeholder="ghp_…", password=True, id="input-pat")
                yield Label(
                    "github.com → Settings → Developer settings → "
                    "Personal access tokens → Tokens (classic)  |  Scopes: repo, read:user",
                    classes="hint",
                )
                yield Label("", id="creds-error", classes="error-label")

            # Step 3b: Self-hosted credentials
            with Vertical(id="step-creds-selfhosted"):
                yield Label("Server URL:", classes="field-label")
                yield Input(placeholder="https://gitlab.example.com", id="input-server-url")
                yield Label("Username:", classes="field-label")
                yield Input(placeholder="your username", id="input-sh-user")
                yield Label("Password / Token:", classes="field-label")
                yield Input(placeholder="••••••••", password=True, id="input-sh-pass")
                yield Label("", id="sh-error", classes="error-label")

            # Step 3c: Local path
            with Vertical(id="step-creds-local"):
                yield Label("Base directory to scan for git repos:", classes="field-label")
                yield Input(placeholder="~/projects", id="input-local-path")
                yield Label(
                    "Nexus will scan this directory for existing git repositories.",
                    classes="hint",
                )

            # Step 4: git config
            with Vertical(id="step-gitconfig"):
                yield Label("Your name (used in commits):", classes="field-label")
                yield Input(placeholder="Jane Doe", id="input-git-name")
                yield Label("Your email (used in commits):", classes="field-label")
                yield Input(placeholder="jane@example.com", id="input-git-email")

            # Step 5: Software check
            with Vertical(id="step-software"):
                yield Label("Checking required software…", classes="field-label")
                yield Log(id="software-log", auto_scroll=True)
                yield Label("", id="software-status")

            # Step 6: Repo selection
            with Vertical(id="step-repos"):
                yield Label("Select repositories to add:", classes="field-label")
                yield Label("", id="repos-hint", classes="hint")
                yield ScrollableContainer(id="repo-list")
                yield Label("", id="repos-error", classes="error-label")

            # Cloning progress
            with Vertical(id="step-clone"):
                yield Label("Setting up repositories…", classes="field-label")
                yield Log(id="clone-log", auto_scroll=True)

            # Done
            with Vertical(id="step-done"):
                yield Label("", id="done-label", classes="ok-label")

            with Horizontal(id="btn-row"):
                yield Button("← Back", id="btn-back")
                yield Button("Next →", id="btn-next", variant="primary")
                yield Button("Finish",  id="btn-finish", variant="success")

        yield Footer()

    def on_mount(self) -> None:
        self._show("step-name")

    # ── Step display ─────────────────────────────────────────────────────────

    def _show(self, step: str) -> None:
        log.debug("Setup step: %s -> %s", self._step, step)
        self._step = step
        for sid in _ALL_STEPS:
            try:
                self.query_one(f"#{sid}").display = (sid == step)
            except Exception:
                pass
        self.query_one("#step-label", Label).update(_STEP_LABELS.get(step, ""))
        self.query_one("#btn-back",   Button).display = step not in ("step-name", "step-clone", "step-done")
        self.query_one("#btn-next",   Button).display = step not in ("step-clone", "step-done", "step-repos")
        self.query_one("#btn-finish", Button).display = step in ("step-repos", "step-done")
        if step == "step-done":
            self.query_one("#btn-finish", Button).label = "Close"

    # ── Button handler ───────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self._go_back()
        elif event.button.id == "btn-next":
            self._advance()
        elif event.button.id == "btn-finish":
            if self._step == "step-repos":
                self.run_worker(self._clone_selected, exclusive=True)
            else:
                self.dismiss()

    def _go_back(self) -> None:
        prev = {
            "step-type":             "step-name",
            "step-creds-github":     "step-type",
            "step-creds-selfhosted": "step-type",
            "step-creds-local":      "step-type",
            "step-gitconfig":        f"step-creds-{self._git_type}",
            "step-software":         "step-gitconfig",
            "step-repos":            "step-software",
        }
        self._show(prev.get(self._step, "step-name"))

    def _advance(self) -> None:
        step = self._step

        if step == "step-name":
            if not self.query_one("#input-name", Input).value.strip():
                self.app.notify("Please enter a name.", severity="error")
                return
            self._show("step-type")

        elif step == "step-type":
            sel = self.query_one("#select-type", Select)
            self._git_type = str(sel.value) if sel.value != Select.BLANK else "github"
            self._show(f"step-creds-{self._git_type}")

        elif step == "step-creds-github":
            token = self.query_one("#input-pat", Input).value.strip()
            if not token:
                self.query_one("#creds-error", Label).update("Please enter a PAT.")
                return
            self._token = token
            self._show("step-gitconfig")

        elif step == "step-creds-selfhosted":
            url  = self.query_one("#input-server-url", Input).value.strip()
            user = self.query_one("#input-sh-user",    Input).value.strip()
            if not url or not user:
                self.query_one("#sh-error", Label).update("Server URL and username are required.")
                return
            self._show("step-gitconfig")

        elif step == "step-creds-local":
            self._show("step-gitconfig")

        elif step == "step-gitconfig":
            self._show("step-software")
            self.run_worker(self._check_software, exclusive=True)

        elif step == "step-software":
            self._show("step-repos")
            self.run_worker(self._load_repos, exclusive=True)

    # ── Workers ──────────────────────────────────────────────────────────────

    async def _check_software(self) -> None:
        from modules.git.git_ops import git_installed, detect_package_manager
        ui_log = self.query_one("#software-log", Log)
        status = self.query_one("#software-status", Label)

        ui_log.write_line("Checking for git…")
        await asyncio.sleep(0.2)

        try:
            installed = git_installed()
        except Exception:
            log.exception("Unexpected error checking for git")
            ui_log.write_line("Error checking for git — see log file.")
            return

        if installed:
            log.info("git is installed")
            ui_log.write_line("✓ git is installed.")
            status.update("All good — press Next to continue.")
            status.add_class("ok-label")
        else:
            log.warning("git not found on this system")
            pm = detect_package_manager()
            ui_log.write_line("✗ git not found.")
            if pm:
                from modules.git.git_ops import install_git_command
                ui_log.write_line("Run this in a terminal:  " + " ".join(install_git_command(pm)))
                ui_log.write_line("Then press Next to continue.")
            else:
                ui_log.write_line("Please install git manually, then press Next.")

    async def _load_repos(self) -> None:
        repo_list = self.query_one("#repo-list", ScrollableContainer)
        hint      = self.query_one("#repos-hint", Label)

        if self._git_type == "github":
            log.info("Fetching GitHub repos for project: %s", self.project.slug)
            hint.update("Fetching your GitHub repositories…")
            try:
                from modules.git.github_api import list_repos
                self._repos = await list_repos(self._token)
                log.info("Fetched %d GitHub repos", len(self._repos))
                hint.update(f"{len(self._repos)} repositories found — select which to add:")
            except Exception as exc:
                log.exception("Failed to fetch GitHub repos")
                hint.update(f"Could not fetch repos: {exc}")
                return

        elif self._git_type == "local":
            from modules.git.git_ops import scan_local_repos
            raw  = self.query_one("#input-local-path", Input).value.strip()
            base = Path(raw).expanduser() if raw else Path.home()
            log.info("Scanning local repos under: %s", base)
            try:
                found = scan_local_repos(base)
            except Exception:
                log.exception("Failed to scan local repos under %s", base)
                hint.update("Error scanning local path — see log file.")
                return
            self._repos = [
                {"name": p.name, "clone_url": str(p), "description": "", "private": False}
                for p in found
            ]
            log.info("Found %d local repos under %s", len(self._repos), base)
            hint.update(f"{len(self._repos)} git repos found — select which to add:")

        else:
            log.debug("Self-hosted: no automatic repo listing")
            hint.update("No automatic listing for self-hosted servers yet — enter repo URLs manually.")
            self._repos = []

        for repo in self._repos:
            await repo_list.mount(RepoCheckRow(repo))

    async def _clone_selected(self) -> None:
        self._show("step-clone")
        ui_log = self.query_one("#clone-log", Log)
        token  = self._token

        selected = [
            row.repo for row in self.query(RepoCheckRow)
            if self.query_one(f"#cb_{row.repo['name']}", Checkbox).value
        ]
        log.info("Clone selected: %d repos for project %s", len(selected), self.project.slug)

        if not selected:
            ui_log.write_line("No repositories selected — skipping clone.")
            self._save_config(repos=[])
            self._finish()
            return

        project_dir = _PROJECTS_DIR / self.project.slug
        repos_dir   = project_dir / "repos"
        try:
            repos_dir.mkdir(exist_ok=True)
        except Exception:
            log.exception("Failed to create repos directory: %s", repos_dir)
            ui_log.write_line(f"Error: could not create {repos_dir}")
            return
        saved = []

        for repo in selected:
            dest = repos_dir / repo["name"]
            if dest.exists():
                log.debug("Repo already cloned, skipping: %s", repo["name"])
                ui_log.write_line(f"  ↩ {repo['name']} already exists, skipping.")
                saved.append({"name": repo["name"], "url": repo["clone_url"],
                              "path": f"repos/{repo['name']}",
                              "last_updated": datetime.now(timezone.utc).isoformat()})
                continue

            ui_log.write_line(f"  Cloning {repo['name']}…")
            await asyncio.sleep(0)

            from modules.git.git_ops import clone_repo
            try:
                ok, msg = await asyncio.get_event_loop().run_in_executor(
                    None, clone_repo, repo["clone_url"], dest, token
                )
            except Exception:
                log.exception("Unexpected error cloning %s", repo["name"])
                ui_log.write_line(f"  ✗ {repo['name']}: unexpected error — see log file")
                continue

            if ok:
                log.info("Cloned: %s", repo["name"])
                ui_log.write_line(f"  ✓ {repo['name']}")
                saved.append({"name": repo["name"], "url": repo["clone_url"],
                              "path": f"repos/{repo['name']}",
                              "last_updated": datetime.now(timezone.utc).isoformat()})
            else:
                log.warning("Clone failed for %s: %s", repo["name"], msg)
                ui_log.write_line(f"  ✗ {repo['name']}: {msg}")

        self._save_config(repos=saved)
        ui_log.write_line("\nDone.")
        self._finish()

    def _save_config(self, repos: list[dict]) -> None:
        cfg_path = _PROJECTS_DIR / self.project.slug / "config.yaml"
        log.info("Saving setup config for %s (%d repos)", self.project.slug, len(repos))
        try:
            with cfg_path.open() as f:
                cfg = yaml.safe_load(f) or {}

            cfg["name"] = self.query_one("#input-name", Input).value.strip() or self.project.name
            cfg["git"]  = {
                "type":       self._git_type,
                "username":   (self.query_one("#input-pat",     Input).value.strip()
                               if self._git_type == "github"
                               else self.query_one("#input-sh-user", Input).value.strip()
                               if self._git_type == "selfhosted" else ""),
                "token":      self._token,
                "server_url": (self.query_one("#input-server-url", Input).value.strip()
                               if self._git_type == "selfhosted" else ""),
                "user_name":  self.query_one("#input-git-name",  Input).value.strip(),
                "user_email": self.query_one("#input-git-email", Input).value.strip(),
                "local_base": (self.query_one("#input-local-path", Input).value.strip()
                               if self._git_type == "local" else ""),
                "repos":      repos,
            }
            with cfg_path.open("w") as f:
                yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
            log.debug("Setup config saved: %s", cfg_path)
        except Exception:
            log.exception("Failed to save setup config for %s", self.project.slug)
            self.app.notify("Failed to save config — see log file.", severity="error")

    def _finish(self) -> None:
        self.query_one("#done-label", Label).update(
            f"✓  {self.project.name} is ready!"
        )
        self._show("step-done")
