from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QToolButton, QLabel, QSizePolicy,
    QDialog, QDialogButtonBox, QLineEdit, QListWidget,
    QPushButton, QMessageBox, QFileDialog, QListWidgetItem,
    QAbstractItemView,
)

from nexus.core.project_manager import (
    ProjectInfo, ensure_module_dirs, auto_configure_module,
    update_project_meta, update_project_path, move_project_files,
)
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

        cfg_btn = QToolButton()
        cfg_btn.setText("⚙")
        cfg_btn.setToolTip("Configure project")
        cfg_btn.setObjectName("modBtnLg")
        cfg_btn.setFixedHeight(_BTN_H)
        cfg_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        cfg_btn.clicked.connect(self._open_config_dialog)
        bar_layout.addWidget(cfg_btn)

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
        # Check if module needs setup first
        try:
            from nexus.core.module_manager import needs_setup_for_module
            if needs_setup_for_module(self._project, module_id):
                self._show_setup_required(module_id)
                return
        except Exception:
            pass
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

    def _show_setup_required(self, module_id: str) -> None:
        info = QWidget()
        layout = QVBoxLayout(info)
        lbl = QLabel(
            f"Module '{module_id}' needs configuration before use.\n\n"
            "Open the TUI to complete setup:\n  uv run nexus"
        )
        lbl.setObjectName("dim")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        self._module_widgets[module_id] = info
        self._stack.addWidget(info)
        self._stack.setCurrentWidget(info)

    def _open_config_dialog(self) -> None:
        dlg = _ProjectConfigDialog(self._project, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        result = dlg.result_data()

        name = result["name"]
        desc = result["description"]
        new_modules = result["modules"]
        path_str = result["path"].strip()

        # Name / description
        if name != self._project.name or desc != self._project.description:
            update_project_meta(self._project.slug, name, desc)
            self._project.name = name
            self._project.description = desc

        # Modules — create dirs for newly added ones
        old_set = set(self._project.modules)
        new_set = set(new_modules)
        if old_set != new_set:
            from nexus.core.config_manager import load_project_config, save_project_config
            cfg = load_project_config(self._project.slug)
            cfg["modules"] = new_modules
            save_project_config(self._project.slug, cfg)
            self._project.modules[:] = new_modules
            for mid in new_set - old_set:
                ensure_module_dirs(self._project.path, mid)
                auto_configure_module(self._project.slug, mid, self._project.path)
            # Invalidate cached widgets for removed modules
            for mid in old_set - new_set:
                self._module_widgets.pop(mid, None)
            self._rebuild_module_buttons()

        # Path
        if path_str:
            new_path = Path(path_str).expanduser()
            try:
                if new_path.resolve() != self._project.path.resolve():
                    ans = QMessageBox.question(
                        self, "Move Project Files?",
                        f"Move all project files to:\n{new_path}\n\n"
                        "Yes = move files   No = update path only",
                        QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                    )
                    if ans == QMessageBox.Cancel:
                        return
                    if ans == QMessageBox.Yes:
                        move_project_files(self._project.slug, new_path)
                    else:
                        update_project_path(self._project.slug, new_path)
                    self._project.path = new_path
            except Exception:
                log.exception("Failed to apply path change for %s", self._project.slug)
                QMessageBox.warning(self, "Error", "Path change failed — see nexus.log.")

    def _rebuild_module_buttons(self) -> None:
        bar_layout = self._icon_bar.layout()
        # Remove all module buttons (they are the ones before the stretch item)
        while bar_layout.count() > 0:
            item = bar_layout.itemAt(0)
            if item and item.spacerItem():
                break
            widget = bar_layout.takeAt(0).widget()
            if widget:
                widget.deleteLater()
        self._build_module_buttons()

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


class _ProjectConfigDialog(QDialog):
    """All-in-one project config: name, description, modules, custom path."""

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(parent)
        self._project = project
        self.setWindowTitle(f"Configure — {project.name}")
        self.setMinimumWidth(520)
        self._build_ui()

    def _build_ui(self) -> None:
        from nexus.core.module_manager import list_feature_modules, list_system_modules
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Name
        layout.addWidget(QLabel("Name:"))
        self._name = QLineEdit(self._project.name)
        layout.addWidget(self._name)

        # Description
        layout.addWidget(QLabel("Description:"))
        self._desc = QLineEdit(self._project.description)
        layout.addWidget(self._desc)

        # Module selector
        layout.addWidget(QLabel("Active modules:"))
        mod_row = QHBoxLayout()

        self._active_list = QListWidget()
        self._active_list.setSelectionMode(QAbstractItemView.SingleSelection)
        for mid in self._project.modules:
            self._active_list.addItem(QListWidgetItem(mid))
        mod_row.addWidget(self._active_list)

        arrow_col = QVBoxLayout()
        arrow_col.setSpacing(4)
        btn_add = QPushButton("← Add")
        btn_add.clicked.connect(self._add_module)
        btn_rm  = QPushButton("Remove →")
        btn_rm.clicked.connect(self._remove_module)
        arrow_col.addStretch()
        arrow_col.addWidget(btn_add)
        arrow_col.addWidget(btn_rm)
        arrow_col.addStretch()
        mod_row.addLayout(arrow_col)

        self._avail_list = QListWidget()
        self._avail_list.setSelectionMode(QAbstractItemView.SingleSelection)
        active_ids = set(self._project.modules)
        for m in list_feature_modules() + list_system_modules():
            if m.id not in active_ids:
                self._avail_list.addItem(QListWidgetItem(m.id))
        mod_row.addWidget(self._avail_list)

        layout.addLayout(mod_row)

        # Path
        layout.addWidget(QLabel("Custom project path (blank = default):"))
        path_row = QHBoxLayout()
        custom_path_str = str(self._project.path) if self._project.path else ""
        self._path = QLineEdit(custom_path_str)
        self._path.setPlaceholderText("~/my-projects/project-name")
        path_row.addWidget(self._path)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_path)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _add_module(self) -> None:
        item = self._avail_list.currentItem()
        if not item:
            return
        mid = item.text()
        self._avail_list.takeItem(self._avail_list.row(item))
        self._active_list.addItem(QListWidgetItem(mid))

    def _remove_module(self) -> None:
        item = self._active_list.currentItem()
        if not item:
            return
        mid = item.text()
        self._active_list.takeItem(self._active_list.row(item))
        self._avail_list.addItem(QListWidgetItem(mid))

    def _browse_path(self) -> None:
        current = self._path.text() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Select Project Directory", current)
        if chosen:
            self._path.setText(chosen)

    def result_data(self) -> dict:
        modules = [
            self._active_list.item(i).text()
            for i in range(self._active_list.count())
        ]
        return {
            "name": self._name.text().strip() or self._project.name,
            "description": self._desc.text().strip(),
            "modules": modules,
            "path": self._path.text().strip(),
        }
