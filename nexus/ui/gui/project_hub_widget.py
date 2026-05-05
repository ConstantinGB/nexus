from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QToolButton, QLabel, QSizePolicy,
)

from nexus.core.project_manager import ProjectInfo
from nexus.core.logger import get

log = get("ui.gui.project_hub_widget")

_ICON_BAR_W = 100  # matches Home tab width
_BTN_H      = 36
_CHAT_W     = 400


class ProjectHubWidget(QWidget):
    """Project hub: module icon bar | content stack | shared input panel.

    Three-panel QHBoxLayout — no manual geometry, no z-order management.
    The input/chat panel lives here at the project level, not inside
    individual modules. Icon bar uses QToolButton to avoid the global
    QPushButton min-width stylesheet rule.
    """

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(parent)
        self._project = project
        self._module_widgets: dict[str, QWidget] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Module icon bar (fixed) ───────────────────────────────────────────
        self._icon_bar = QWidget()
        self._icon_bar.setFixedWidth(_ICON_BAR_W)
        self._icon_bar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        bar_layout = QVBoxLayout(self._icon_bar)
        bar_layout.setContentsMargins(4, 4, 4, 4)
        bar_layout.setSpacing(4)
        bar_layout.setAlignment(Qt.AlignTop)

        self._build_module_buttons()

        bar_layout.addStretch()

        input_btn = QToolButton()
        input_btn.setText("⌨")
        input_btn.setToolTip("Toggle input panel")
        input_btn.setObjectName("modBtnLg")
        input_btn.setFixedHeight(_BTN_H)
        input_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        input_btn.clicked.connect(self._toggle_chat)
        bar_layout.addWidget(input_btn)

        root.addWidget(self._icon_bar)

        # ── Module content stack (flexible) ──────────────────────────────────
        self._stack = QStackedWidget()
        placeholder = QWidget()
        ph_layout = QVBoxLayout(placeholder)
        ph_lbl = QLabel(f"Select a module\nfor {self._project.name}")
        ph_lbl.setObjectName("dim")
        ph_lbl.setAlignment(Qt.AlignCenter)
        ph_layout.addWidget(ph_lbl)
        self._stack.addWidget(placeholder)
        root.addWidget(self._stack, 1)

        # ── Shared input / chat panel (fixed width) ───────────────────────────
        from nexus.ui.gui.chat_panel import ChatPanel
        skill_scopes = ["global"] + list(self._project.modules)
        self._chat = ChatPanel(
            slug         = self._project.slug,
            module_key   = self._project.module,
            skill_scopes = skill_scopes,
            parent       = self,
        )
        self._chat.setFixedWidth(_CHAT_W)
        root.addWidget(self._chat)

    def _build_module_buttons(self) -> None:
        from nexus.core.module_manager import get_module
        bar_layout = self._icon_bar.layout()
        for mid in self._project.modules:
            info = get_module(mid)
            name = info.name if info else mid
            label = name[:8].upper()
            btn = QToolButton()
            btn.setText(label)
            btn.setToolTip(name)
            btn.setObjectName("modBtn")
            btn.setFixedHeight(_BTN_H)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda checked=False, m=mid: self._open_module(m))
            bar_layout.addWidget(btn)

    # ── Module loading ────────────────────────────────────────────────────────

    def _open_module(self, module_id: str) -> None:
        if module_id in self._module_widgets:
            self._stack.setCurrentWidget(self._module_widgets[module_id])
            return
        widget = self._load_module_widget(module_id)
        if widget is None:
            self._show_load_error(module_id)
            return
        self._module_widgets[module_id] = widget
        self._stack.addWidget(widget)
        self._stack.setCurrentWidget(widget)

    def _load_module_widget(self, module_id: str) -> QWidget | None:
        import importlib
        from PySide6.QtWidgets import QMainWindow
        try:
            mod = importlib.import_module(f"modules.{module_id}.gui_screen")
            cls = getattr(mod, "GuiScreen", None)
            if not cls:
                log.warning("No GuiScreen class in modules.%s.gui_screen", module_id)
                return None
            widget = cls(self._project, parent=None)
            if isinstance(widget, QMainWindow):
                central = widget.takeCentralWidget()
                if central is not None:
                    central._hub_screen = widget
                    return central
            return widget
        except Exception:
            log.exception("Failed to load gui_screen for module %s", module_id)
        return None

    def _show_load_error(self, module_id: str) -> None:
        err = QWidget()
        layout = QVBoxLayout(err)
        lbl = QLabel(
            f"Failed to load module: {module_id}\n\n"
            "Check the application log for details.\n"
            "logs/nexus.log"
        )
        lbl.setObjectName("dim")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(lbl)
        self._stack.addWidget(err)
        self._stack.setCurrentWidget(err)

    # ── Chat toggle ───────────────────────────────────────────────────────────

    def _toggle_chat(self) -> None:
        self._chat.setVisible(not self._chat.isVisible())

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        self._chat.closeEvent(event)
        for w in self._module_widgets.values():
            target = getattr(w, "_hub_screen", w)
            if hasattr(target, "closeEvent"):
                try:
                    target.closeEvent(event)
                except Exception:
                    pass
        super().closeEvent(event)
