from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLabel,
)

from nexus.core.project_manager import ProjectInfo
from nexus.core.logger import get

log = get("ui.gui.project_hub_widget")


class ProjectHubWidget(QWidget):
    """Project hub: left module icon bar + swappable content area.

    Each module's GuiScreen is lazy-loaded into a QStackedWidget on first click.
    The ⌨ button at the bottom of the icon bar toggles the active module's own
    chat panel (if it has a `_chat` attribute).  No separate hub-level input
    panel is created — module screens own their chat/terminal UI.
    """

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(parent)
        self._project = project
        self._module_widgets: dict[str, QWidget] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left icon bar (fixed 52 px)
        self._icon_bar = QWidget()
        self._icon_bar.setFixedWidth(52)
        bar_layout = QVBoxLayout(self._icon_bar)
        bar_layout.setContentsMargins(2, 4, 2, 4)
        bar_layout.setSpacing(2)
        bar_layout.setAlignment(Qt.AlignTop)
        layout.addWidget(self._icon_bar)

        # Content area
        self._stack = QStackedWidget()
        placeholder = QWidget()
        ph_layout = QVBoxLayout(placeholder)
        ph_lbl = QLabel(f"Select a module\nfor {self._project.name}")
        ph_lbl.setObjectName("dim")
        ph_lbl.setAlignment(Qt.AlignCenter)
        ph_layout.addWidget(ph_lbl)
        self._stack.addWidget(placeholder)
        layout.addWidget(self._stack, 1)

        # Build one button per active module
        self._build_module_buttons()

        # ⌨ toggle at bottom — hides/shows the active module's chat panel
        bar_layout.addStretch()
        input_btn = QPushButton("⌨")
        input_btn.setToolTip("Toggle chat panel")
        input_btn.setFixedSize(44, 44)
        input_btn.clicked.connect(self._toggle_chat)
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
            # insert before the trailing stretch
            bar_layout.insertWidget(bar_layout.count() - 1, btn)

    # ── Module loading ────────────────────────────────────────────────────────

    def _open_module(self, module_id: str) -> None:
        if module_id in self._module_widgets:
            self._stack.setCurrentWidget(self._module_widgets[module_id])
            return
        widget = self._load_module_widget(module_id)
        if widget is None:
            return
        # Hide the module's embedded chat panel by default; ⌨ reveals it
        if hasattr(widget, "_chat"):
            widget._chat.setVisible(False)
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

    # ── Chat toggle ───────────────────────────────────────────────────────────

    def _toggle_chat(self) -> None:
        w = self._stack.currentWidget()
        if w and hasattr(w, "_chat"):
            w._chat.setVisible(not w._chat.isVisible())

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        for w in self._module_widgets.values():
            if hasattr(w, "closeEvent"):
                try:
                    w.closeEvent(event)
                except Exception:
                    pass
        super().closeEvent(event)
