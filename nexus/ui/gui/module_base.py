from __future__ import annotations

import subprocess
from typing import Callable

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QFormLayout,
    QMessageBox, QFrame,
)

from nexus.core.project_manager import ProjectInfo
from nexus.core.config_manager import load_project_config

log = __import__("nexus.core.logger", fromlist=["get"]).get("ui.gui.module_base")


class _CmdWorker(QThread):
    line_ready   = Signal(str)
    finished_rc  = Signal(int)

    def __init__(self, cmd: list[str], cwd: str | None = None, env=None, parent=None) -> None:
        super().__init__(parent)
        self._cmd = cmd
        self._cwd = cwd
        self._env = env

    def run(self) -> None:
        try:
            proc = subprocess.Popen(
                self._cmd,
                cwd=self._cwd,
                env=self._env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            for line in proc.stdout:
                self.line_ready.emit(line.rstrip())
            proc.wait()
            self.finished_rc.emit(proc.returncode)
        except FileNotFoundError:
            self.line_ready.emit(f"[error] command not found: {self._cmd[0]!r}")
            self.finished_rc.emit(1)
        except Exception as exc:
            self.line_ready.emit(f"[error] {exc}")
            self.finished_rc.emit(1)


class ModuleGuiBase(QWidget):
    """Shared layout scaffold for module GUI screens.

    Subclass contract:
    - Override _build_toolbar() and call _add_btn() to populate the action bar.
    - Override _build_extra() to insert widgets between the info panel and log.
    - Call _set_info([(key, val), ...]) to populate the key/value info panel.
    - Call _append(text) to write to the output log.
    - Call _run_cmd([...], cwd=...) to run a subprocess streamed to the log.

    The chat/input panel lives at the ProjectHubWidget level, not per-module.
    SKILL_SCOPES is retained as documentation for each module's AI scope.
    """

    SKILL_SCOPES: list[str] | None = None

    def __init__(self, project: ProjectInfo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project  = project
        self._cfg     = load_project_config(project.slug)
        self._workers: list[_CmdWorker] = []
        self._build_base_ui()

    # ── Base layout ───────────────────────────────────────────────────────────

    def _build_base_ui(self) -> None:
        vbox = QVBoxLayout(self)
        vbox.setSpacing(6)
        vbox.setContentsMargins(8, 8, 8, 8)

        # ── Toolbar ──────────────────────────────────────────────────────────
        self._toolbar_layout = QHBoxLayout()
        self._toolbar_layout.setSpacing(6)
        self._build_toolbar()
        self._toolbar_layout.addStretch()
        vbox.addLayout(self._toolbar_layout)

        # ── Info panel ───────────────────────────────────────────────────────
        self._info_widget = QWidget()
        self._info_form   = QFormLayout(self._info_widget)
        self._info_form.setSpacing(4)
        self._info_form.setContentsMargins(4, 4, 4, 4)
        vbox.addWidget(self._info_widget)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        vbox.addWidget(sep)

        # ── Extra content area ───────────────────────────────────────────────
        self._extra_widget = QWidget()
        self._extra_layout = QVBoxLayout(self._extra_widget)
        self._extra_layout.setContentsMargins(0, 0, 0, 0)
        self._build_extra()
        if self._extra_layout.count():
            vbox.addWidget(self._extra_widget)

        # ── Output log ───────────────────────────────────────────────────────
        log_lbl = QLabel("Output")
        log_lbl.setObjectName("subtitle")
        vbox.addWidget(log_lbl)

        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setMinimumHeight(100)
        vbox.addWidget(self._output)

    # ── Overridable hooks ─────────────────────────────────────────────────────

    def _build_toolbar(self) -> None:
        """Override; call _add_btn() to add action buttons."""

    def _build_extra(self) -> None:
        """Override to insert widgets between info panel and output log."""

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _add_btn(self, label: str, callback: Callable, primary: bool = False) -> QPushButton:
        btn = QPushButton(label)
        if primary:
            btn.setObjectName("primary")
        btn.clicked.connect(callback)
        self._toolbar_layout.addWidget(btn)
        return btn

    def _set_info(self, rows: list[tuple[str, str]]) -> None:
        while self._info_form.rowCount():
            self._info_form.removeRow(0)
        for key, val in rows:
            k = QLabel(key)
            k.setObjectName("subtitle")
            v = QLabel(str(val) if val else "—")
            v.setTextInteractionFlags(Qt.TextSelectableByMouse)
            v.setWordWrap(True)
            self._info_form.addRow(k, v)

    def _append(self, text: str) -> None:
        self._output.append(text)

    def _run_cmd(self, cmd: list[str], cwd: str | None = None, env=None) -> _CmdWorker:
        self._append(f"$ {' '.join(cmd)}")
        worker = _CmdWorker(cmd, cwd=cwd, env=env, parent=self)
        worker.line_ready.connect(self._append)
        worker.finished_rc.connect(lambda rc: self._append(f"[exit {rc}]"))
        self._workers.append(worker)
        worker.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)
        worker.start()
        return worker

    def _not_implemented(self, feature: str = "This feature") -> None:
        QMessageBox.information(
            self, "Not yet implemented",
            f"{feature} is not yet available in the GUI.\n\n"
            "Use the TUI:  uv run nexus",
        )

    def closeEvent(self, event) -> None:
        super().closeEvent(event)
