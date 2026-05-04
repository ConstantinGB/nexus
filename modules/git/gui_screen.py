from __future__ import annotations
import asyncio
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QListWidget, QListWidgetItem, QTextEdit,
    QLabel, QInputDialog, QMessageBox,
)

from nexus.core.project_manager import ProjectInfo
from nexus.core.config_manager import load_project_config
from nexus.ui.gui.base_project_window import BaseProjectWindow
from nexus.ui.gui.chat_panel import ChatPanel

_PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"


class _GitWorker(QThread):
    output_ready = Signal(str)
    finished_ok  = Signal()
    error        = Signal(str)

    def __init__(self, cmd: list[str], cwd: Path) -> None:
        super().__init__()
        self._cmd = cmd
        self._cwd = cwd

    def run(self) -> None:
        try:
            result = subprocess.run(
                self._cmd, cwd=self._cwd,
                capture_output=True, text=True, timeout=60,
            )
            out = (result.stdout + result.stderr).strip()
            self.output_ready.emit(out or "(no output)")
            if result.returncode == 0:
                self.finished_ok.emit()
            else:
                self.error.emit(f"Exit {result.returncode}")
        except Exception as exc:
            self.error.emit(str(exc))


class GuiScreen(BaseProjectWindow):
    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"Git — {project.name}")

        cfg        = load_project_config(project.slug)
        self._git  = cfg.get("git", {})
        self._repos = self._git.get("repos", [])
        self._proj_dir = _PROJECTS_DIR / project.slug

        splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(splitter)

        # Left: repo list + actions
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 4, 8)

        self._repo_list = QListWidget()
        for r in self._repos:
            self._repo_list.addItem(r.get("name", "unknown"))
        self._repo_list.currentRowChanged.connect(self._on_repo_selected)
        left_layout.addWidget(QLabel("Repositories:"))
        left_layout.addWidget(self._repo_list, 1)

        btn_grid = QHBoxLayout()
        for label, slot in [("Status", self._status), ("Pull", self._pull), ("Push", self._push)]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            btn_grid.addWidget(btn)
        left_layout.addLayout(btn_grid)

        btn_grid2 = QHBoxLayout()
        for label, slot in [("Log", self._log), ("Diff", self._diff)]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            btn_grid2.addWidget(btn)
        left_layout.addLayout(btn_grid2)

        splitter.addWidget(left)

        # Right: output log + chat panel
        right = QSplitter(Qt.Vertical)

        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setPlaceholderText("Select a repo and run an action…")
        right.addWidget(self._output)

        self._chat = ChatPanel(
            slug         = project.slug,
            module_key   = "git",
            skill_scopes = ["global", "git"],
        )
        right.addWidget(self._chat)
        right.setSizes([300, 300])

        splitter.addWidget(right)
        splitter.setSizes([240, 700])

        self._worker: _GitWorker | None = None

    def _current_repo(self) -> dict | None:
        row = self._repo_list.currentRow()
        if row < 0 or row >= len(self._repos):
            return None
        return self._repos[row]

    def _repo_path(self, repo: dict) -> Path:
        return self._proj_dir / repo.get("path", f"repos/{repo['name']}")

    def _run_git(self, args: list[str]) -> None:
        repo = self._current_repo()
        if not repo:
            self._output.append("No repo selected.")
            return
        path = self._repo_path(repo)
        if not path.exists():
            self._output.append(f"Repo path not found: {path}")
            return
        if self._worker and self._worker.isRunning():
            self._output.append("(command already running…)")
            return
        cmd = ["git"] + args
        self._output.append(f"\n$ git {' '.join(args)}")
        self._worker = _GitWorker(cmd, path)
        self._worker.output_ready.connect(self._output.append)
        self._worker.start()

    def _on_repo_selected(self, row: int) -> None:
        if row < 0:
            return
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

    def closeEvent(self, event) -> None:
        if hasattr(self, "_chat"):
            self._chat.closeEvent(event)
        super().closeEvent(event)
