from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QScrollArea, QVBoxLayout, QGridLayout,
    QFrame, QLabel, QPushButton, QSizePolicy,
)

from nexus.core.project_manager import ProjectInfo, list_projects
from nexus.ui.gui.theme import (
    BG, SURFACE, SURFACE2, ACCENT_G, ACCENT_B, ACCENT_P, ACCENT_M, TEXT, TEXT_DIM
)

def _display_name(project: ProjectInfo) -> str:
    from nexus.core.module_manager import MODULE_PREFIX
    prefix = MODULE_PREFIX.get(project.module, "")
    name = project.name
    if prefix and name.lower().startswith(prefix + "-"):
        name = name[len(prefix) + 1:]
    return name


_MODULE_COLOURS: dict[str, str] = {
    "operator":  ACCENT_G,
    "git":       ACCENT_B,
    "research":  ACCENT_P,
    "journal":   "#FFD700",
    "codex":     "#FF8C00",
    "org":       "#20B2AA",
    "web":       "#87CEEB",
    "game":      ACCENT_M,
    "backup":    "#90EE90",
    "server":    "#FFA07A",
    "vault":     "#DDA0DD",
    "security":  "#FF6347",
    "custom":    "#F0E68C",
}

_TILE_W = 220
_TILE_H = 130


def _module_colour(module: str) -> str:
    return _MODULE_COLOURS.get(module, ACCENT_P)


class _ProjectTile(QFrame):
    opened = Signal(object)  # ProjectInfo

    def __init__(self, project: ProjectInfo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project = project
        colour        = _module_colour(project.module)

        self.setFixedSize(_TILE_W, _TILE_H)
        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            _ProjectTile {{
                background: {SURFACE};
                border: 1px solid {SURFACE2};
                border-radius: 8px;
            }}
            _ProjectTile:hover {{
                border-color: {colour};
                background: #2a1a45;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        badge = QLabel(project.module.upper())
        badge.setStyleSheet(f"color: {colour}; font-size: 10px; font-weight: bold; background: transparent;")
        badge.setAlignment(Qt.AlignCenter)
        layout.addWidget(badge)

        name = QLabel(_display_name(project))
        name.setStyleSheet(f"color: {TEXT}; font-size: 14px; font-weight: bold; background: transparent;")
        name.setWordWrap(True)
        name.setAlignment(Qt.AlignCenter)
        layout.addWidget(name)

        layout.addStretch(1)

        desc = QLabel(project.description or "No description")
        desc.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; background: transparent;")
        desc.setWordWrap(True)
        desc.setMaximumHeight(32)
        desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.opened.emit(self._project)
        super().mousePressEvent(event)


class _AddTile(QFrame):
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(_TILE_W, _TILE_H)
        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            _AddTile {{
                background: {BG};
                border: 2px dashed {SURFACE2};
                border-radius: 8px;
            }}
            _AddTile:hover {{
                border-color: {ACCENT_G};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        plus = QLabel("+")
        plus.setStyleSheet(f"color: {ACCENT_G}; font-size: 36px; background: transparent;")
        plus.setAlignment(Qt.AlignCenter)
        layout.addWidget(plus)

        lbl = QLabel("New Project")
        lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px; background: transparent;")
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


_SCROLLBAR_RESERVE = 20   # px subtracted to pre-account for vertical scrollbar width


class TileGrid(QScrollArea):
    open_project = Signal(object)   # ProjectInfo
    add_project  = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self._container = QWidget()
        self._grid      = QGridLayout(self._container)
        self._grid.setSpacing(16)
        self._grid.setContentsMargins(24, 24, 24, 24)
        self.setWidget(self._container)

        self._current_cols = 0
        self.refresh()

    def _calc_cols(self) -> int:
        # Subtract a scrollbar reserve so column count is identical whether or not
        # the vertical scrollbar is visible — prevents the oscillation loop where
        # the scrollbar appearing reduces viewport width just enough to reflow to
        # fewer columns, which changes content height, which hides the scrollbar, repeat.
        usable = self.viewport().width() - _SCROLLBAR_RESERVE - 48
        if usable < _TILE_W:
            return 1
        return max(1, usable // (_TILE_W + 16))

    def refresh(self) -> None:
        cols = self._calc_cols()
        self._current_cols = cols

        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        projects = list_projects()
        for idx, project in enumerate(projects):
            tile = _ProjectTile(project, self._container)
            tile.opened.connect(self.open_project)
            self._grid.addWidget(tile, idx // cols, idx % cols)

        add_idx = len(projects)
        add     = _AddTile(self._container)
        add.clicked.connect(self.add_project)
        self._grid.addWidget(add, add_idx // cols, add_idx % cols)

        # Reset all column stretches then pin the trailing filler column so tiles
        # align left instead of spreading across the full width.
        for c in range(cols + 1):
            self._grid.setColumnStretch(c, 0)
        self._grid.setColumnStretch(cols, 1)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Only rebuild if the number of columns actually changes — avoids triggering
        # a full grid rebuild (and potential re-layout cascade) on every pixel of resize.
        if self._calc_cols() != self._current_cols:
            self.refresh()
