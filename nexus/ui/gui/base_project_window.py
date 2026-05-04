from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QFrame,
)

from nexus.core.project_manager import ProjectInfo


class BaseProjectWindow(QMainWindow):
    """Minimal project window. Module GUI screens subclass this."""

    def __init__(self, project: ProjectInfo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project = project
        self.setWindowTitle(f"Nexus — {project.name}  [{project.module}]")
        self.setMinimumSize(960, 640)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.statusBar().showMessage(f"{project.slug}  ·  {project.module}")
        self._build_fallback_ui()

    def _build_fallback_ui(self) -> None:
        """Show module info when no dedicated gui_screen.py exists."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        badge = QLabel(self.project.module.upper())
        badge.setObjectName("title")
        badge.setAlignment(Qt.AlignCenter)
        layout.addWidget(badge)

        name_label = QLabel(self.project.name)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #E0E0FF;")
        layout.addWidget(name_label)

        if self.project.description:
            desc = QLabel(self.project.description)
            desc.setObjectName("dim")
            desc.setAlignment(Qt.AlignCenter)
            layout.addWidget(desc)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #3A2260;")
        layout.addWidget(sep)

        hint = QLabel(
            f"No GUI screen available for  {self.project.module}  yet.\n\n"
            f"Open in TUI:   uv run nexus open {self.project.name}"
        )
        hint.setObjectName("dim")
        hint.setAlignment(Qt.AlignCenter)
        hint.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(hint)

        self.setCentralWidget(container)

    def closeEvent(self, event) -> None:
        if hasattr(self, "_chat"):
            self._chat.closeEvent(event)
        super().closeEvent(event)
