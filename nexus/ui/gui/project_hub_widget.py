from __future__ import annotations
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLabel, QComboBox,
)

from nexus.core.project_manager import ProjectInfo
from nexus.core.logger import get

log = get("ui.gui.project_hub_widget")


class ProjectHubWidget(QWidget):
    """Project hub: left module icon bar + swappable content area + input panel."""

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(parent)
        self._project = project
        self._module_widgets: dict[str, QWidget] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left icon bar
        self._icon_bar = QWidget()
        self._icon_bar.setFixedWidth(52)
        bar_layout = QVBoxLayout(self._icon_bar)
        bar_layout.setContentsMargins(2, 4, 2, 4)
        bar_layout.setSpacing(2)
        bar_layout.setAlignment(Qt.AlignTop)
        layout.addWidget(self._icon_bar)

        # Content area
        self._stack = QStackedWidget()
        # Placeholder
        placeholder = QWidget()
        ph_layout = QVBoxLayout(placeholder)
        ph_lbl = QLabel(f"Select a module\nfor {self._project.name}")
        ph_lbl.setObjectName("dim")
        ph_lbl.setAlignment(Qt.AlignCenter)
        ph_layout.addWidget(ph_lbl)
        self._stack.addWidget(placeholder)
        layout.addWidget(self._stack, 1)

        # Input panel (right side, initially hidden)
        self._input_panel = self._build_input_panel()
        self._input_panel.setVisible(False)
        layout.addWidget(self._input_panel)

        # Build module buttons
        self._build_module_buttons()

        # Input toggle at bottom of icon bar
        bar_layout.addStretch()
        input_btn = QPushButton("⌨")   # ⌨
        input_btn.setToolTip("Open input panel (AI / Claude / Shell)")
        input_btn.setFixedSize(44, 44)
        input_btn.clicked.connect(self._toggle_input_panel)
        bar_layout.addWidget(input_btn)

    def _build_module_buttons(self) -> None:
        from nexus.core.module_manager import get_module
        bar_layout = self._icon_bar.layout()
        for mid in self._project.modules:
            info = get_module(mid)
            label = (info.name[:4] if info else mid[:4]).upper()
            btn = QPushButton(label)
            btn.setToolTip(info.name if info else mid)
            btn.setFixedSize(44, 44)
            btn.clicked.connect(lambda checked=False, m=mid: self._open_module(m))
            # Insert before the stretch (second-to-last item)
            bar_layout.insertWidget(bar_layout.count() - 1, btn)

    def _build_input_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(380)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        # Mode selector row
        mode_row = QHBoxLayout()
        mode_lbl = QLabel("Input:")
        mode_lbl.setObjectName("subtitle")
        mode_row.addWidget(mode_lbl)
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["AI Chat", "Claude", "Shell"])
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self._mode_combo, 1)
        layout.addLayout(mode_row)

        # Stacked input panels
        self._input_stack = QStackedWidget()

        # Index 0: AI Chat
        try:
            from nexus.ui.gui.chat_panel import ChatPanel
            self._chat_panel = ChatPanel(
                slug=self._project.slug,
                module_key=self._project.module or "custom",
                skill_scopes=["global"] + list(self._project.modules),
                parent=self,
            )
            self._input_stack.addWidget(self._chat_panel)
        except Exception:
            log.exception("Failed to create ChatPanel for hub")
            self._chat_panel = None
            placeholder = QLabel("Chat unavailable")
            self._input_stack.addWidget(placeholder)

        # Index 1: Claude PTY
        project_dir = str(self._project.path)
        try:
            from nexus.ui.gui.pty_terminal import PtyTerminalWidget
            self._claude_term = PtyTerminalWidget("claude", cwd=project_dir, parent=self)
            self._input_stack.addWidget(self._claude_term)
        except Exception:
            log.exception("Failed to create claude PTY terminal")
            self._claude_term = None
            self._input_stack.addWidget(QLabel("Claude terminal unavailable"))

        # Index 2: Shell PTY
        try:
            from nexus.ui.gui.pty_terminal import PtyTerminalWidget
            self._shell_term = PtyTerminalWidget("bash -i", cwd=project_dir, parent=self)
            self._input_stack.addWidget(self._shell_term)
        except Exception:
            log.exception("Failed to create shell PTY terminal")
            self._shell_term = None
            self._input_stack.addWidget(QLabel("Shell terminal unavailable"))

        layout.addWidget(self._input_stack, 1)
        return panel

    def _toggle_input_panel(self) -> None:
        visible = self._input_panel.isVisible()
        self._input_panel.setVisible(not visible)
        if not visible:
            idx = self._mode_combo.currentIndex()
            self._activate_input_mode(idx)

    def _on_mode_changed(self, idx: int) -> None:
        if self._input_panel.isVisible():
            self._activate_input_mode(idx)

    def _activate_input_mode(self, idx: int) -> None:
        self._input_stack.setCurrentIndex(idx)
        if idx == 1 and self._claude_term is not None:
            self._claude_term.start()
        elif idx == 2 and self._shell_term is not None:
            self._shell_term.start()

    def _open_module(self, module_id: str) -> None:
        if module_id in self._module_widgets:
            self._stack.setCurrentWidget(self._module_widgets[module_id])
            return
        widget = self._load_module_widget(module_id)
        if widget is None:
            return
        self._module_widgets[module_id] = widget
        self._stack.addWidget(widget)
        self._stack.setCurrentWidget(widget)

    def _load_module_widget(self, module_id: str) -> QWidget | None:
        import importlib
        try:
            mod = importlib.import_module(f"modules.{module_id}.gui_screen")
            cls = getattr(mod, "GuiScreen", None)
            if cls:
                return cls(self._project, parent=None)
        except Exception:
            log.exception("Failed to load gui_screen for module %s", module_id)
        return None

    def closeEvent(self, event) -> None:
        if self._claude_term is not None:
            try:
                self._claude_term.stop()
            except Exception:
                pass
        if self._shell_term is not None:
            try:
                self._shell_term.stop()
            except Exception:
                pass
        if self._chat_panel is not None and hasattr(self._chat_panel, "closeEvent"):
            try:
                self._chat_panel.closeEvent(event)
            except Exception:
                pass
        for w in self._module_widgets.values():
            if hasattr(w, "closeEvent"):
                try:
                    w.closeEvent(event)
                except Exception:
                    pass
        super().closeEvent(event)
