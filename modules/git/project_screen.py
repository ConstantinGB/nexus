from __future__ import annotations
import asyncio
from pathlib import Path

import yaml
from textual.app import ComposeResult
from textual.screen import Screen, ModalScreen
from textual.widgets import (
    Header, Footer, Label, Button, Checkbox, TextArea, Log, Input,
)
from textual.containers import Vertical, Horizontal, ScrollableContainer

from nexus.core.logger import get
from nexus.core.platform import open_path
from nexus.core.project_manager import ProjectInfo

log = get("git.project_screen")

_PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"


# ── Commit modal (with diff preview) ─────────────────────────────────────────

class CommitModal(ModalScreen):
    DEFAULT_CSS = """
    CommitModal { align: center middle; }
    #cm-box {
        background: #2D1B4E; border: solid #00B4FF;
        padding: 1 2; width: 72; height: auto; max-height: 36;
    }
    #cm-title       { color: #00B4FF; text-style: bold; height: 2; }
    .cm-section     { color: #00FF88; height: 1; margin-top: 1; }
    .cm-hint        { color: #8080AA; height: 1; }
    #cm-diff-log    { height: 8; background: #0A0518; border: solid #3A2260; margin-bottom: 1; }
    #cm-msg         { height: 5; margin-top: 1; }
    #cm-btns        { height: 3; margin-top: 1; }
    #cm-btns Button { margin-right: 1; }
    """

    def __init__(self, repo_name: str, repo_path: Path) -> None:
        super().__init__()
        self.repo_name = repo_name
        self.repo_path = repo_path

    def compose(self) -> ComposeResult:
        with Vertical(id="cm-box"):
            yield Label(f"Commit & Push — {self.repo_name}", id="cm-title")
            yield Label("Changed files (will be staged with git add -A):", classes="cm-section")
            yield Log(id="cm-diff-log", auto_scroll=False)
            yield Label("Commit message:", classes="cm-section")
            yield TextArea("", id="cm-msg")
            with Horizontal(id="cm-btns"):
                yield Button("Commit & Push", id="btn-do-commit", variant="success")
                yield Button("Cancel",        id="btn-cancel")

    def on_mount(self) -> None:
        self.run_worker(self._load_status())

    async def _load_status(self) -> None:
        from modules.git.git_ops import get_short_status
        status = await asyncio.get_event_loop().run_in_executor(
            None, get_short_status, self.repo_path
        )
        ui_log = self.query_one("#cm-diff-log", Log)
        if status:
            for line in status.splitlines():
                ui_log.write_line(line)
        else:
            ui_log.write_line("(working tree clean — nothing to commit)")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-do-commit":
            msg = self.query_one("#cm-msg", TextArea).text.strip()
            if not msg:
                self.app.notify("Please enter a commit message.", severity="error")
                return
            self.dismiss(msg)


# ── Branch modal ──────────────────────────────────────────────────────────────

class BranchModal(ModalScreen):
    DEFAULT_CSS = """
    BranchModal { align: center middle; }
    #br-box {
        background: #2D1B4E; border: solid #00B4FF;
        padding: 1 2; width: 64; height: auto; max-height: 38;
    }
    #br-title      { color: #00B4FF; text-style: bold; height: 2; }
    .br-section    { color: #00FF88; height: 1; margin-top: 1; }
    .br-current    { color: #FFAA00; height: 1; margin-bottom: 1; }
    #br-list       { height: 10; border: solid #3A2260; margin-bottom: 1; }
    .br-item       { color: #E0E0FF; }
    .br-item-cur   { color: #FFAA00; text-style: bold; }
    .br-remote     { color: #555588; }
    #br-new-label  { color: #00FF88; height: 1; margin-top: 1; }
    #br-new-input  { margin-bottom: 1; }
    #br-del-label  { color: #00FF88; height: 1; margin-top: 1; }
    #br-del-input  { margin-bottom: 1; }
    #br-del-btns   { height: 3; margin-bottom: 1; }
    #br-del-btns Button { margin-right: 1; }
    #br-btns       { height: 3; }
    #br-btns Button { margin-right: 1; }
    #br-error      { color: #FF4444; height: 1; }
    """

    def __init__(self, repo_name: str, repo_path: Path, current_branch: str) -> None:
        super().__init__()
        self.repo_name      = repo_name
        self.repo_path      = repo_path
        self._current       = current_branch
        self._local_branches: list[str] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="br-box"):
            yield Label(f"Branches — {self.repo_name}", id="br-title")
            yield Label(f"Current: {self._current}", classes="br-current")
            yield Label("Local branches (click to switch):", classes="br-section")
            yield ScrollableContainer(id="br-list")
            yield Label("New branch:", id="br-new-label")
            yield Input(placeholder="feature/my-branch", id="br-new-input")
            yield Label("Delete branch (cannot be current):", id="br-del-label")
            yield Input(placeholder="old-feature-branch", id="br-del-input")
            with Horizontal(id="br-del-btns"):
                yield Button("Delete",       id="btn-br-delete",  variant="error")
                yield Button("Force Delete", id="btn-br-force")
            yield Label("", id="br-error")
            with Horizontal(id="br-btns"):
                yield Button("Create & Switch", id="btn-br-create", variant="primary")
                yield Button("Open PR ↗",       id="btn-br-pr")
                yield Button("Cancel",          id="btn-br-cancel")

    def on_mount(self) -> None:
        self.run_worker(self._load_branches())

    async def _load_branches(self) -> None:
        from modules.git.git_ops import get_branches
        branches = await asyncio.get_event_loop().run_in_executor(
            None, get_branches, self.repo_path
        )
        local   = [b for b in branches if not b.startswith("remotes/")]
        remote  = [b for b in branches if b.startswith("remotes/")]
        self._local_branches = local
        br_list = self.query_one("#br-list", ScrollableContainer)
        await br_list.remove_children()
        for i, b in enumerate(local):
            is_cur = (b == self._current)
            btn = Button(
                ("● " if is_cur else "  ") + b,
                id=f"bri-{i}",
                classes="br-item-cur" if is_cur else "br-item",
            )
            await br_list.mount(btn)
        for b in remote[:6]:
            await br_list.mount(Label(f"  {b}", classes="br-remote"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-br-cancel":
            self.dismiss(None)
        elif bid == "btn-br-create":
            name = self.query_one("#br-new-input", Input).value.strip()
            if not name:
                self.query_one("#br-error", Label).update("Enter a branch name.")
                return
            self.run_worker(self._create(name))
        elif bid in ("btn-br-delete", "btn-br-force"):
            name = self.query_one("#br-del-input", Input).value.strip()
            if not name:
                self.query_one("#br-error", Label).update("Enter the branch name to delete.")
                return
            if name == self._current:
                self.query_one("#br-error", Label).update("Cannot delete the current branch.")
                return
            self.run_worker(self._delete(name, force=(bid == "btn-br-force")))
        elif bid == "btn-br-pr":
            self.run_worker(self._open_pr())
        elif bid and bid.startswith("bri-"):
            idx = int(bid[4:])
            branch = self._local_branches[idx]
            if branch != self._current:
                self.run_worker(self._switch(branch))

    async def _switch(self, branch: str) -> None:
        from modules.git.git_ops import checkout_branch
        ok, msg = await asyncio.get_event_loop().run_in_executor(
            None, checkout_branch, self.repo_path, branch
        )
        if ok:
            self.dismiss(("switched", branch))
        else:
            self.query_one("#br-error", Label).update(msg[:120])
            self.app.notify(f"Switch failed: {msg[:120]}", severity="error")

    async def _create(self, name: str) -> None:
        from modules.git.git_ops import create_branch
        ok, msg = await asyncio.get_event_loop().run_in_executor(
            None, create_branch, self.repo_path, name
        )
        if ok:
            self.dismiss(("created", name))
        else:
            self.query_one("#br-error", Label).update(msg[:120])
            self.app.notify(f"Create failed: {msg[:120]}", severity="error")

    async def _delete(self, name: str, force: bool = False) -> None:
        from modules.git.git_ops import delete_branch
        ok, msg = await asyncio.get_event_loop().run_in_executor(
            None, delete_branch, self.repo_path, name, force
        )
        if ok:
            self.dismiss(("deleted", name))
        else:
            hint = " (use Force Delete if unmerged)" if not force and "not fully merged" in msg else ""
            self.query_one("#br-error", Label).update(msg[:120] + hint)
            self.app.notify(f"Delete failed: {msg[:120]}", severity="error")

    async def _open_pr(self) -> None:
        import subprocess as _sp
        from modules.git.git_ops import get_remote_url, pr_url
        remote = await asyncio.get_event_loop().run_in_executor(
            None, get_remote_url, self.repo_path
        )
        url = pr_url(remote, self._current)
        if url:
            _sp.Popen(open_path(url))
            self.app.notify(f"Opening PR for '{self._current}'…", severity="information")
        elif not remote:
            self.app.notify("No remote 'origin' configured.", severity="warning")
        elif self._current in ("main", "master", "develop"):
            self.app.notify("Switch to a feature branch first.", severity="warning")
        else:
            self.app.notify("Only GitHub and GitLab remotes are supported.", severity="warning")


# ── Stash modal ───────────────────────────────────────────────────────────────

class StashModal(ModalScreen):
    DEFAULT_CSS = """
    StashModal { align: center middle; }
    #st-box {
        background: #2D1B4E; border: solid #00B4FF;
        padding: 1 2; width: 64; height: auto; max-height: 24;
    }
    #st-title      { color: #00B4FF; text-style: bold; height: 2; }
    .st-section    { color: #00FF88; height: 1; margin-top: 1; }
    #st-list       { height: 8; border: solid #3A2260; margin-bottom: 1; }
    .st-item       { color: #E0E0FF; }
    .st-empty      { color: #555588; }
    #st-btns       { height: 3; }
    #st-btns Button { margin-right: 1; }
    """

    def __init__(self, repo_name: str, repo_path: Path) -> None:
        super().__init__()
        self.repo_name = repo_name
        self.repo_path = repo_path
        self._stashes: list[str] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="st-box"):
            yield Label(f"Stash — {self.repo_name}", id="st-title")
            yield Label("Stash list:", classes="st-section")
            yield ScrollableContainer(id="st-list")
            with Horizontal(id="st-btns"):
                yield Button("Stash Changes", id="btn-st-push", variant="primary")
                yield Button("Pop Latest",    id="btn-st-pop",  disabled=True)
                yield Button("Cancel",        id="btn-st-cancel")

    def on_mount(self) -> None:
        self.run_worker(self._load_stashes())

    async def _load_stashes(self) -> None:
        from modules.git.git_ops import list_stashes
        self._stashes = await asyncio.get_event_loop().run_in_executor(
            None, list_stashes, self.repo_path
        )
        st_list = self.query_one("#st-list", ScrollableContainer)
        await st_list.remove_children()
        if self._stashes:
            for s in self._stashes:
                await st_list.mount(Label(s, classes="st-item"))
            self.query_one("#btn-st-pop", Button).disabled = False
        else:
            await st_list.mount(Label("No stashes.", classes="st-empty"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-st-cancel":
            self.dismiss(None)
        elif bid == "btn-st-push":
            self.run_worker(self._do_push())
        elif bid == "btn-st-pop":
            self.run_worker(self._do_pop())

    async def _do_push(self) -> None:
        from modules.git.git_ops import stash_push
        ok, msg = await asyncio.get_event_loop().run_in_executor(
            None, stash_push, self.repo_path
        )
        if ok:
            self.dismiss(("pushed", msg))
        else:
            self.app.notify(f"Stash failed: {msg[:120]}", severity="error")

    async def _do_pop(self) -> None:
        from modules.git.git_ops import stash_pop
        ok, msg = await asyncio.get_event_loop().run_in_executor(
            None, stash_pop, self.repo_path
        )
        if ok:
            self.dismiss(("popped", msg))
        else:
            self.app.notify(f"Pop failed: {msg[:120]}", severity="error")


# ── Info modal ────────────────────────────────────────────────────────────────

class InfoModal(ModalScreen):
    DEFAULT_CSS = """
    InfoModal { align: center middle; }
    #modal-box {
        background: #2D1B4E; border: solid #00B4FF;
        padding: 1 2; width: 70; height: 30;
    }
    #modal-title   { color: #00B4FF; text-style: bold; height: 2; }
    .info-section  { color: #00FF88; text-style: bold; margin-top: 1; height: 1; }
    .info-item     { color: #E0E0FF; padding-left: 2; }
    #modal-btns    { height: 3; margin-top: 1; }
    """

    def __init__(self, repo_name: str, repo_path: Path) -> None:
        super().__init__()
        self.repo_name = repo_name
        self.repo_path = repo_path

    def compose(self) -> ComposeResult:
        from modules.git.git_ops import get_branches, get_recent_commits, get_repo_status
        status   = get_repo_status(self.repo_path)
        branches = get_branches(self.repo_path)
        commits  = get_recent_commits(self.repo_path, n=8)

        with ScrollableContainer(id="modal-box"):
            yield Label(f"Info — {self.repo_name}", id="modal-title")
            yield Label("Current branch:", classes="info-section")
            yield Label(f"  {status.get('branch', '?')}", classes="info-item")
            yield Label("All branches:", classes="info-section")
            for b in branches[:12]:
                yield Label(f"  {b}", classes="info-item")
            yield Label("Recent commits:", classes="info-section")
            for c in commits:
                yield Label(
                    f"  {c['hash']}  {c['message'][:48]}  ({c['date']})",
                    classes="info-item",
                )
            with Horizontal(id="modal-btns"):
                yield Button("Close", id="btn-close", variant="primary")

    def on_button_pressed(self, _: Button.Pressed) -> None:
        self.dismiss()


# ── Confirm-delete modal ──────────────────────────────────────────────────────

class ConfirmDeleteModal(ModalScreen):
    DEFAULT_CSS = """
    ConfirmDeleteModal { align: center middle; }
    #modal-box {
        background: #2D1B4E; border: solid #FF4444;
        padding: 1 2; width: 60; height: auto;
    }
    #modal-title  { color: #FF4444; text-style: bold; height: 2; }
    .modal-hint   { color: #8080AA; height: 1; }
    .delete-item  { color: #E0E0FF; padding-left: 2; }
    #modal-btns   { height: 3; margin-top: 2; }
    #modal-btns Button { margin-right: 1; }
    """

    def __init__(self, names: list[str]) -> None:
        super().__init__()
        self.names = names

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-box"):
            yield Label("Delete repositories?", id="modal-title")
            yield Label("This permanently removes the local copies:", classes="modal-hint")
            for n in self.names:
                yield Label(f"  • {n}", classes="delete-item")
            with Horizontal(id="modal-btns"):
                yield Button("Yes, delete", id="btn-yes", variant="error")
                yield Button("Cancel",      id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-yes")


# ── Add-repo modal ────────────────────────────────────────────────────────────

class AddRepoModal(ModalScreen):
    DEFAULT_CSS = """
    AddRepoModal { align: center middle; }
    #ar-box {
        background: #2D1B4E; border: solid #00B4FF;
        padding: 1 2; width: 72; height: auto; max-height: 30;
    }
    #ar-title     { color: #00B4FF; text-style: bold; height: 2; }
    .ar-label     { color: #00FF88; height: 1; margin-top: 1; }
    .ar-hint      { color: #555588; height: 2; }
    .ar-error     { color: #FF4444; height: 1; }
    #ar-log       { height: 10; background: #0A0518; border: solid #3A2260; margin-top: 1; }
    #ar-btns      { height: 3; margin-top: 1; }
    #ar-btns Button { margin-right: 1; }
    """

    def __init__(self, project_dir: Path, token: str = "") -> None:
        super().__init__()
        self._project_dir = project_dir
        self._token = token
        self._cloned_repo: dict | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="ar-box"):
            yield Label("Add Repository", id="ar-title")
            with Vertical(id="ar-form"):
                yield Label("Repository URL:", classes="ar-label")
                yield Label(
                    "SSH:   git@github.com:user/repo.git\n"
                    "HTTPS: https://github.com/user/repo.git",
                    classes="ar-hint",
                )
                yield Input(placeholder="git@github.com:user/repo.git", id="ar-url")
                yield Label("Name (auto-filled):", classes="ar-label")
                yield Input(placeholder="repo-name", id="ar-name")
                yield Label("", id="ar-error", classes="ar-error")
            with Vertical(id="ar-progress"):
                yield Log(id="ar-log", auto_scroll=True)
            with Horizontal(id="ar-btns"):
                yield Button("Clone",  id="btn-ar-clone",  variant="primary")
                yield Button("Cancel", id="btn-ar-cancel")
                yield Button("Done",   id="btn-ar-done",   variant="success")

    def on_mount(self) -> None:
        self.query_one("#ar-progress").display = False
        self.query_one("#btn-ar-done").display = False

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "ar-url":
            name = self._derive_name(event.value.strip())
            if name:
                self.query_one("#ar-name", Input).value = name

    @staticmethod
    def _derive_name(url: str) -> str:
        if not url:
            return ""
        if not url.startswith("http") and ":" in url:
            path_part = url.split(":", 1)[1]
        else:
            path_part = url.rstrip("/")
        name = path_part.rstrip("/").split("/")[-1]
        if name.endswith(".git"):
            name = name[:-4]
        return name

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-ar-cancel":
            self.dismiss(None)
        elif bid == "btn-ar-done":
            self.dismiss(self._cloned_repo)
        elif bid == "btn-ar-clone":
            self._start_clone()

    def _start_clone(self) -> None:
        url  = self.query_one("#ar-url",  Input).value.strip()
        name = self.query_one("#ar-name", Input).value.strip() or self._derive_name(url)
        if not url:
            self.query_one("#ar-error", Label).update("Enter a repository URL.")
            return
        if not name:
            self.query_one("#ar-error", Label).update("Could not derive a name — please enter one.")
            return
        dest = self._project_dir / "repos" / name
        if dest.exists():
            self.query_one("#ar-error", Label).update(f"'{name}' already exists in this project.")
            return
        self.query_one("#ar-form").display = False
        self.query_one("#ar-progress").display = True
        self.query_one("#btn-ar-clone").display = False
        self.query_one("#btn-ar-cancel").display = False
        self.run_worker(self._do_clone(url, name, dest))

    async def _do_clone(self, url: str, name: str, dest: Path) -> None:
        from datetime import datetime, timezone
        from modules.git.git_ops import clone_repo
        ui_log = self.query_one("#ar-log", Log)
        ui_log.write_line(f"Cloning {url}")
        ui_log.write_line(f"  → {dest}")
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            ui_log.write_line(f"✗ Could not create directory: {exc}")
            self.query_one("#btn-ar-cancel").display = True
            return
        try:
            ok, msg = await asyncio.get_event_loop().run_in_executor(
                None, clone_repo, url, dest, self._token
            )
        except Exception as exc:
            ui_log.write_line(f"✗ Unexpected error: {exc}")
            self.query_one("#btn-ar-cancel").display = True
            return
        if ok:
            ui_log.write_line("✓ Cloned successfully.")
            self._cloned_repo = {
                "name": name,
                "url":  url,
                "path": f"repos/{name}",
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }
            self.query_one("#btn-ar-done").display = True
        else:
            ui_log.write_line(f"✗ Clone failed: {msg}")
            self.query_one("#ar-form").display = True
            self.query_one("#ar-progress").display = False
            self.query_one("#ar-error", Label).update(f"Clone failed: {msg[:80]}")
            self.query_one("#btn-ar-clone").display = True
            self.query_one("#btn-ar-cancel").display = True


# ── Per-repo row ──────────────────────────────────────────────────────────────

class RepoRow(Vertical):
    DEFAULT_CSS = """
    RepoRow {
        height: auto;
        background: #2D1B4E;
        border-bottom: solid #241540;
        padding: 1 2;
        margin-bottom: 0;
    }
    RepoRow:hover { background: #3A2260; }

    RepoRow #row-info    { height: 1; margin-bottom: 1; }
    RepoRow #row-buttons { height: 3; }
    RepoRow #row-buttons Button { margin-right: 1; width: auto; min-width: 8; }

    RepoRow .repo-name   { color: #E0E0FF; text-style: bold; width: 24; }
    RepoRow .repo-branch { color: #00B4FF; width: 18; }
    RepoRow .repo-time   { color: #555588; width: 1fr; }

    RepoRow .status-ok   { color: #00FF88; }
    RepoRow .status-warn { color: #FFAA00; }
    RepoRow .status-err  { color: #FF4444; }
    RepoRow .status-load { color: #555588; }
    """

    def __init__(self, repo: dict, project_dir: Path, delete_mode: bool = False, **kwargs) -> None:
        super().__init__(id=f"row_{repo['name']}", **kwargs)
        self.repo        = repo
        self.project_dir = project_dir
        self.delete_mode = delete_mode

    @property
    def repo_path(self) -> Path:
        return self.project_dir / self.repo.get("path", f"repos/{self.repo['name']}")

    def compose(self) -> ComposeResult:
        name = self.repo["name"]
        with Horizontal(id="row-info"):
            if self.delete_mode:
                yield Checkbox("", id=f"del_{name}")
            yield Label(name,       classes="repo-name",   id=f"lbl_name_{name}")
            yield Label("⎇ …",     classes="repo-branch", id=f"lbl_branch_{name}")
            yield Label("loading…", classes="status-load", id=f"lbl_status_{name}")
            yield Label("",         classes="repo-time",   id=f"lbl_time_{name}")
        with Horizontal(id="row-buttons"):
            yield Button("Pull",   id=f"pull_{name}")
            yield Button("Push",   id=f"push_{name}")
            yield Button("Commit", id=f"commit_{name}")
            yield Button("Branch", id=f"branch_{name}")
            yield Button("Stash",  id=f"stash_{name}")
            yield Button("Info",   id=f"info_{name}")

    def on_mount(self) -> None:
        self.run_worker(self._load_status, exclusive=False)

    async def _load_status(self) -> None:
        from modules.git.git_ops import get_repo_status, get_last_updated, fetch_remote
        path = self.repo_path
        name = self.repo["name"]
        log.debug("Loading status for repo: %s", name)
        if not path.exists():
            self._set_status("not cloned", "status-warn")
            return
        try:
            await asyncio.get_event_loop().run_in_executor(None, fetch_remote, path)
            status = await asyncio.get_event_loop().run_in_executor(None, get_repo_status, path)
            last   = await asyncio.get_event_loop().run_in_executor(None, get_last_updated, path)
            self.query_one(f"#lbl_branch_{name}", Label).update(f"⎇ {status['branch']}")
            self.query_one(f"#lbl_time_{name}",   Label).update(f"updated {last}")
        except Exception:
            log.exception("Failed to load status for repo: %s", name)
            self._set_status("status error", "status-err")
            return
        if status["behind"] > 0:
            self._set_status(f"↓ {status['behind']} behind", "status-warn")
        elif status["ahead"] > 0:
            self._set_status(f"↑ {status['ahead']} ahead", "status-warn")
        elif status["dirty"]:
            self._set_status("uncommitted changes", "status-warn")
        else:
            self._set_status("✓ up to date", "status-ok")

    def _set_status(self, text: str, css_class: str) -> None:
        try:
            lbl = self.query_one(f"#lbl_status_{self.repo['name']}", Label)
            lbl.update(text)
            for c in ("status-ok", "status-warn", "status-err", "status-load"):
                lbl.remove_class(c)
            lbl.add_class(css_class)
        except Exception:
            pass

    def current_branch(self) -> str:
        """Return the branch name shown in the row label (best-effort)."""
        try:
            text = self.query_one(f"#lbl_branch_{self.repo['name']}", Label).renderable
            return str(text).lstrip("⎇ ").strip()
        except Exception:
            return ""


# ── Main screen ───────────────────────────────────────────────────────────────

class GitProjectScreen(Screen):
    BINDINGS = [("escape", "dismiss", "Back")]

    DEFAULT_CSS = """
    GitProjectScreen { background: #1A0A2E; }
    GitProjectScreen Header { background: #2D1B4E; color: #00B4FF; }
    GitProjectScreen Footer { background: #2D1B4E; color: #00FF88; }

    #top-bar {
        height: 3;
        background: #2D1B4E;
        padding: 0 2;
        border-bottom: solid #3A2260;
    }
    #project-title { color: #00B4FF; text-style: bold; width: 1fr; }
    #project-meta  { color: #8080AA; }

    #action-bar {
        height: 3;
        padding: 0 2;
        background: #241540;
        border-bottom: solid #3A2260;
    }
    #action-bar Button  { margin-right: 1; }
    #btn-delete         { border: solid #FF4444; color: #FF4444; }

    #repo-scroll  { height: 1fr; }
    #no-repos     { color: #555588; padding: 2 4; }

    #delete-confirm-bar {
        height: 3;
        padding: 0 2;
        background: #2A0A0A;
        border-top: solid #FF4444;
    }
    #delete-confirm-bar Button { margin-right: 1; }
    """

    def __init__(self, project: ProjectInfo) -> None:
        super().__init__()
        self.project      = project
        self._git_cfg     = {}
        self._repos: list[dict] = []
        self._delete_mode = False

    def _load_cfg(self) -> None:
        cfg_path = _PROJECTS_DIR / self.project.slug / "config.yaml"
        log.debug("Loading config for project: %s", self.project.slug)
        try:
            with cfg_path.open() as f:
                cfg = yaml.safe_load(f) or {}
            self._git_cfg = cfg.get("git", {})
            self._repos   = self._git_cfg.get("repos", [])
        except Exception:
            log.exception("Failed to load config for project: %s", self.project.slug)
            self._git_cfg = {}
            self._repos   = []

    def compose(self) -> ComposeResult:
        self._load_cfg()
        git_type = self._git_cfg.get("type", "git")
        username = self._git_cfg.get("username", "")
        if git_type == "github" and username:
            display_user = username[:4] + "••••••••"
        else:
            display_user = username
        meta = git_type.upper() + (f" · {display_user}" if display_user else "")

        yield Header()
        with Horizontal(id="top-bar"):
            yield Label(self.project.name, id="project-title")
            yield Label(meta,              id="project-meta")
        with Horizontal(id="action-bar"):
            yield Button("Pull All",    id="btn-pull-all")
            yield Button("Clone / Add", id="btn-clone-add")
            yield Button("Delete",      id="btn-delete")
        yield ScrollableContainer(id="repo-scroll")
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._render_repos)

    # ── Render ────────────────────────────────────────────────────────────────

    async def _render_repos(self) -> None:
        scroll = self.query_one("#repo-scroll", ScrollableContainer)
        await scroll.remove_children()
        project_dir = _PROJECTS_DIR / self.project.slug

        if not self._repos:
            await scroll.mount(
                Label("No repositories yet. Use 'Clone / Add' to add one.", id="no-repos")
            )
            return

        for repo in self._repos:
            await scroll.mount(RepoRow(repo, project_dir, delete_mode=self._delete_mode))

        if self._delete_mode:
            await scroll.mount(
                Horizontal(
                    Button("Confirm Delete", id="btn-confirm-delete", variant="error"),
                    Button("Cancel",         id="btn-cancel-delete"),
                    id="delete-confirm-bar",
                )
            )

    # ── Button handler ────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        try:
            self._handle_button(bid)
        except Exception:
            log.exception("Unhandled error in on_button_pressed (button=%s)", bid)
            self.app.notify("An unexpected error occurred — see log.", severity="error")

    def _repo_path(self, repo_name: str) -> Path:
        repo_meta = next((r for r in self._repos if r["name"] == repo_name), None)
        if not repo_meta:
            return _PROJECTS_DIR / self.project.slug / "repos" / repo_name
        return _PROJECTS_DIR / self.project.slug / repo_meta.get("path", f"repos/{repo_name}")

    def _handle_button(self, bid: str | None) -> None:
        if bid == "btn-pull-all":
            self.run_worker(self._pull_all())

        elif bid == "btn-clone-add":
            token = self._git_cfg.get("token", "")
            project_dir = _PROJECTS_DIR / self.project.slug
            self.app.push_screen(AddRepoModal(project_dir, token), self._on_repo_added)

        elif bid == "btn-delete":
            self._delete_mode = True
            self.query_one("#btn-delete", Button).disabled = True
            self.run_worker(self._render_repos())

        elif bid == "btn-cancel-delete":
            self._delete_mode = False
            self.query_one("#btn-delete", Button).disabled = False
            self.run_worker(self._render_repos())

        elif bid == "btn-confirm-delete":
            checked = [
                row.repo["name"]
                for row in self.query(RepoRow)
                if self.query_one(f"#del_{row.repo['name']}", Checkbox).value
            ]
            if not checked:
                self.app.notify("No repositories selected.", severity="warning")
                return
            self.app.push_screen(ConfirmDeleteModal(checked), self._handle_delete_result)

        elif bid and bid.startswith("pull_"):
            self.run_worker(self._pull_one(bid[5:]))

        elif bid and bid.startswith("push_"):
            self.run_worker(self._push_one(bid[5:]))

        elif bid and bid.startswith("commit_"):
            repo_name = bid[7:]
            path = self._repo_path(repo_name)
            self.app.push_screen(
                CommitModal(repo_name, path),
                lambda msg, r=repo_name: self.run_worker(self._do_commit(r, msg)) if msg else None,
            )

        elif bid and bid.startswith("branch_"):
            repo_name = bid[7:]
            path = self._repo_path(repo_name)
            try:
                row = self.query_one(f"#row_{repo_name}", RepoRow)
                current = row.current_branch()
            except Exception:
                current = ""
            self.app.push_screen(
                BranchModal(repo_name, path, current),
                lambda result, r=repo_name: self._on_branch_result(result, r),
            )

        elif bid and bid.startswith("stash_"):
            repo_name = bid[6:]
            path = self._repo_path(repo_name)
            self.app.push_screen(
                StashModal(repo_name, path),
                lambda result, r=repo_name: self._on_stash_result(result, r),
            )

        elif bid and bid.startswith("info_"):
            repo_name = bid[5:]
            self.app.push_screen(InfoModal(repo_name, self._repo_path(repo_name)))

    # ── Async operations ──────────────────────────────────────────────────────

    async def _pull_all(self) -> None:
        from modules.git.git_ops import pull_repo
        project_dir = _PROJECTS_DIR / self.project.slug
        for repo in self._repos:
            path = project_dir / repo.get("path", f"repos/{repo['name']}")
            if not path.exists():
                continue
            self.app.notify(f"Pulling {repo['name']}…")
            try:
                ok, msg = await asyncio.get_event_loop().run_in_executor(None, pull_repo, path)
            except Exception:
                log.exception("Unexpected error pulling %s", repo["name"])
                self.app.notify(f"✗ {repo['name']}: unexpected error", severity="error")
                continue
            self.app.notify(
                f"{'✓' if ok else '✗'} {repo['name']}: {msg[:120]}",
                severity="information" if ok else "error",
            )
        await self._render_repos()

    async def _pull_one(self, repo_name: str) -> None:
        from modules.git.git_ops import pull_repo
        path = self._repo_path(repo_name)
        self.app.notify(f"Pulling {repo_name}…")
        try:
            ok, msg = await asyncio.get_event_loop().run_in_executor(None, pull_repo, path)
        except Exception:
            log.exception("Unexpected error pulling %s", repo_name)
            self.app.notify(f"✗ {repo_name}: unexpected error", severity="error")
            return
        self.app.notify(f"{'✓' if ok else '✗'} {msg[:80]}",
                        severity="information" if ok else "error")
        await self._render_repos()

    async def _push_one(self, repo_name: str) -> None:
        from modules.git.git_ops import push_repo
        path = self._repo_path(repo_name)
        self.app.notify(f"Pushing {repo_name}…")
        try:
            ok, msg = await asyncio.get_event_loop().run_in_executor(None, push_repo, path)
        except Exception:
            log.exception("Unexpected error pushing %s", repo_name)
            self.app.notify(f"✗ {repo_name}: unexpected error", severity="error")
            return
        self.app.notify(f"{'✓' if ok else '✗'} {msg[:80]}",
                        severity="information" if ok else "error")

    async def _do_commit(self, repo_name: str, message: str) -> None:
        from modules.git.git_ops import commit_and_push
        path = self._repo_path(repo_name)
        self.app.notify(f"Committing & pushing {repo_name}…")
        try:
            ok, msg = await asyncio.get_event_loop().run_in_executor(
                None, commit_and_push, path, message
            )
        except Exception:
            log.exception("Unexpected error in commit+push for %s", repo_name)
            self.app.notify(f"✗ {repo_name}: unexpected error", severity="error")
            return
        self.app.notify(f"{'✓' if ok else '✗'} {msg[:80]}",
                        severity="information" if ok else "error")
        await self._render_repos()

    def _on_branch_result(self, result: tuple | None, repo_name: str) -> None:
        if not result:
            return
        action, branch = result
        verb = {"switched": "Switched to", "created": "Created", "deleted": "Deleted"}.get(action, action)
        self.app.notify(f"{verb} branch '{branch}' in {repo_name}.")
        self.run_worker(self._render_repos())

    def _on_stash_result(self, result: tuple | None, repo_name: str) -> None:
        if not result:
            return
        action, msg = result
        verb = "Stashed" if action == "pushed" else "Popped"
        self.app.notify(f"{verb} changes in {repo_name}. {msg[:50]}")
        self.run_worker(self._render_repos())

    def _handle_delete_result(self, confirmed: bool) -> None:
        if not confirmed:
            return
        from modules.git.git_ops import delete_repo
        project_dir = _PROJECTS_DIR / self.project.slug
        to_delete = [
            row.repo["name"]
            for row in self.query(RepoRow)
            if self.query_one(f"#del_{row.repo['name']}", Checkbox).value
        ]
        for name in to_delete:
            repo_meta = next((r for r in self._repos if r["name"] == name), None)
            if not repo_meta:
                continue
            path = project_dir / repo_meta.get("path", f"repos/{name}")
            if path.exists():
                try:
                    delete_repo(path)
                except Exception:
                    log.exception("Failed to delete repo directory: %s", path)
                    self.app.notify(f"✗ Failed to delete {name}", severity="error")
                    continue
            self._repos = [r for r in self._repos if r["name"] != name]
            self.app.notify(f"Deleted {name}.")

        self._save_repos()
        self._delete_mode = False
        self.query_one("#btn-delete", Button).disabled = False
        self.run_worker(self._render_repos())

    def _on_repo_added(self, repo: dict | None) -> None:
        if not repo:
            return
        self._repos.append(repo)
        self._save_repos()
        self.run_worker(self._render_repos())
        self.app.notify(f"'{repo['name']}' added.")

    def _save_repos(self) -> None:
        cfg_path = _PROJECTS_DIR / self.project.slug / "config.yaml"
        try:
            with cfg_path.open() as f:
                cfg = yaml.safe_load(f) or {}
            cfg.setdefault("git", {})["repos"] = self._repos
            with cfg_path.open("w") as f:
                yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
        except Exception:
            log.exception("Failed to save repos config for %s", self.project.slug)
            self.app.notify("Failed to save config.", severity="error")
