from __future__ import annotations
from pathlib import Path

from PySide6.QtWidgets import QListWidget, QLabel

from nexus.core.project_manager import ProjectInfo
from nexus.ui.gui.module_base import ModuleGuiBase

_PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"

log = __import__("nexus.core.logger", fromlist=["get"]).get("git.gui_screen")


class GuiScreen(ModuleGuiBase):
    SKILL_SCOPES = ["global", "git"]

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)  # _build_extra populates _repos + _repo_list
        self.setWindowTitle(f"Git — {project.name}")
        self._set_info([("Repos", str(len(self._repos)))])

    # ── Layout hooks ─────────────────────────────────────────────────────────

    def _build_toolbar(self) -> None:
        for label, slot in [
            ("Status", self._status),
            ("Pull",   self._pull),
            ("Push",   self._push),
            ("Log",    self._log),
            ("Diff",   self._diff),
        ]:
            self._add_btn(label, slot)

    def _build_extra(self) -> None:
        # self._cfg is set by ModuleGuiBase.__init__ before _build_base_ui calls this
        self._repos: list[dict] = self._cfg.get("git", {}).get("repos", [])
        lbl = QLabel("Repositories:")
        lbl.setObjectName("subtitle")
        self._extra_layout.addWidget(lbl)
        self._repo_list = QListWidget()
        for r in self._repos:
            self._repo_list.addItem(r.get("name", "unknown"))
        self._repo_list.currentRowChanged.connect(self._on_repo_selected)
        self._extra_layout.addWidget(self._repo_list)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _current_repo(self) -> dict | None:
        row = self._repo_list.currentRow()
        if row < 0 or row >= len(self._repos):
            return None
        return self._repos[row]

    def _repo_path(self, repo: dict) -> Path:
        return _PROJECTS_DIR / self.project.slug / repo.get("path", f"repos/{repo['name']}")

    def _run_git(self, args: list[str]) -> None:
        repo = self._current_repo()
        if not repo:
            self._append("No repo selected.")
            return
        path = self._repo_path(repo)
        if not path.exists():
            self._append(f"Repo path not found: {path}")
            return
        self._run_cmd(["git"] + args, cwd=str(path))

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_repo_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._repos):
            return
        repo = self._repos[row]
        self._set_info([
            ("Repos",    str(len(self._repos))),
            ("Selected", repo.get("name", "?")),
        ])
        self._status()

    def _status(self) -> None:
        self._run_git(["status", "--short", "--branch"])

    def _pull(self) -> None:
        self._run_git(["pull", "--ff-only"])

    def _push(self) -> None:
        self._run_git(["push"])

    def _log(self) -> None:
        self._run_git(["log", "--oneline", "-20"])

    def _diff(self) -> None:
        self._run_git(["diff", "--stat"])
