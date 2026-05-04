from __future__ import annotations
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeyEvent
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QDialog, QDialogButtonBox,
    QFormLayout, QLineEdit, QLabel, QVBoxLayout,
    QWidget, QToolBar, QMessageBox, QTabWidget, QToolButton,
    QSizePolicy, QTabBar,
)

from nexus.core.logger import get
from nexus.core.module_manager import list_feature_modules, list_system_modules
from nexus.core.project_manager import create_project, ProjectInfo
from nexus.ui.gui.theme import get_gui_theme, DEFAULT_GUI_THEME, ACCENT_G
from nexus.ui.gui.tile_grid import TileGrid

log = get("ui.gui.app")


class _AddProjectDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setMinimumWidth(500)
        self.setMinimumHeight(500)

        from PySide6.QtWidgets import QListWidget, QListWidgetItem, QAbstractItemView

        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setSpacing(10)

        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Daily Driver")
        form.addRow("Name:", self._name)

        self._desc = QLineEdit()
        self._desc.setPlaceholderText("Optional description")
        form.addRow("Description:", self._desc)

        layout.addLayout(form)

        # Feature modules list
        feat_lbl = QLabel("Feature modules (select one or more):")
        layout.addWidget(feat_lbl)
        self._feat_list = QListWidget()
        self._feat_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self._feat_list.setMaximumHeight(180)
        for m in list_feature_modules():
            item = QListWidgetItem(f"{m.name}  —  {m.description[:50]}")
            item.setData(Qt.UserRole, m.id)
            self._feat_list.addItem(item)
        layout.addWidget(self._feat_list)

        # System tools list
        sys_lbl = QLabel("System tools (optional):")
        layout.addWidget(sys_lbl)
        self._sys_list = QListWidget()
        self._sys_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self._sys_list.setMaximumHeight(120)
        for m in list_system_modules():
            item = QListWidgetItem(f"{m.name}  —  {m.description[:50]}")
            item.setData(Qt.UserRole, m.id)
            self._sys_list.addItem(item)
        layout.addWidget(self._sys_list)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_result(self) -> tuple[str, list[str], str]:
        modules: list[str] = []
        for item in self._feat_list.selectedItems():
            modules.append(item.data(Qt.UserRole))
        for item in self._sys_list.selectedItems():
            modules.append(item.data(Qt.UserRole))
        return (
            self._name.text().strip(),
            modules,
            self._desc.text().strip(),
        )


class NexusGuiApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Nexus")
        self.setMinimumSize(1100, 700)

        # Load saved theme (default to legacy)
        from nexus.core.config_manager import load_global_config
        cfg = load_global_config()
        self._theme_name = cfg.get("ui", {}).get("gui_theme", DEFAULT_GUI_THEME)
        self.setStyleSheet(get_gui_theme(self._theme_name))

        # Tab widget
        self._tabs = QTabWidget(self)
        self._tabs.setTabsClosable(True)
        self._tabs.tabCloseRequested.connect(self._close_tab)
        self.setCentralWidget(self._tabs)

        # Home tab — permanent, no close button
        self._grid = TileGrid()
        self._grid.open_project.connect(self._open_project)
        self._grid.add_project.connect(self._add_project)
        self._tabs.addTab(self._grid, "🏠 Home")
        self._tabs.tabBar().setTabButton(0, QTabBar.RightSide, None)

        # "+" corner button to add a new project
        add_btn = QToolButton(self)
        add_btn.setText("  +  ")
        add_btn.setToolTip("New project")
        add_btn.clicked.connect(self._add_project)
        self._tabs.setCornerWidget(add_btn, Qt.TopRightCorner)

        # Track open project tabs: slug → tab index
        self._open_slugs: dict[str, int] = {}

        self._build_toolbar()
        self._build_statusbar()

    # ── Status bar ────────────────────────────────────────────────────────────

    def _build_statusbar(self) -> None:
        from nexus.ui.gui.theme import TEXT_DIM
        hint = QLabel("  Nexus — GUI   ESC: Home   Ctrl+Q: Close tab   Ctrl+PgUp/Dn: Switch tab  ")
        hint.setStyleSheet(f"color: {TEXT_DIM}; background: transparent;")
        self.statusBar().addPermanentWidget(hint)

    # ── Keybindings ───────────────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key  = event.key()
        mods = event.modifiers()
        ctrl = mods & Qt.ControlModifier

        if key == Qt.Key_Escape:
            self._tabs.setCurrentIndex(0)
            event.accept()
            return

        if ctrl and key == Qt.Key_Q:
            self._close_tab(self._tabs.currentIndex())
            event.accept()
            return

        if ctrl and key == Qt.Key_PageUp:
            count = self._tabs.count()
            if count > 1:
                idx = (self._tabs.currentIndex() - 1) % count
                self._tabs.setCurrentIndex(idx)
            event.accept()
            return

        if ctrl and key == Qt.Key_PageDown:
            count = self._tabs.count()
            if count > 1:
                idx = (self._tabs.currentIndex() + 1) % count
                self._tabs.setCurrentIndex(idx)
            event.accept()
            return

        super().keyPressEvent(event)

    # ── Theme ─────────────────────────────────────────────────────────────────

    def apply_theme(self, name: str) -> None:
        self._theme_name = name
        self.setStyleSheet(get_gui_theme(name))

    # ── Toolbar ───────────────────────────────────────────────────────────────

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main", self)
        tb.setMovable(False)
        self.addToolBar(tb)

        title = QLabel("  NEXUS  ")
        title.setStyleSheet(
            f"color: {ACCENT_G}; font-size: 15px; font-weight: bold; background: transparent;"
        )
        tb.addWidget(title)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        spacer.setStyleSheet("background: transparent;")
        tb.addWidget(spacer)

        settings_action = QAction("⚙ Settings", self)
        settings_action.triggered.connect(self._open_settings)
        tb.addAction(settings_action)

        refresh_action = QAction("⟳ Refresh", self)
        refresh_action.triggered.connect(self._grid.refresh)
        tb.addAction(refresh_action)

    # ── Open project in tab ───────────────────────────────────────────────────

    def _open_project(self, project: ProjectInfo) -> None:
        # Bring existing tab to front if already open
        if project.slug in self._open_slugs:
            self._tabs.setCurrentIndex(self._open_slugs[project.slug])
            return

        from nexus.ui.gui.project_hub_widget import ProjectHubWidget
        hub = ProjectHubWidget(project, parent=None)

        from nexus.ui.gui.tile_grid import _display_name
        label = _display_name(project)
        idx = self._tabs.addTab(hub, f"  {label}")
        self._open_slugs[project.slug] = idx
        self._tabs.setCurrentIndex(idx)

    def _close_tab(self, idx: int) -> None:
        if idx == 0:   # Home tab is permanent
            return
        # Find and remove slug from tracking
        slug = next((s for s, i in self._open_slugs.items() if i == idx), None)
        if slug:
            del self._open_slugs[slug]
        self._tabs.removeTab(idx)
        # Reindex remaining slugs (all tabs after the removed one shift down by 1)
        self._open_slugs = {
            s: i if i < idx else i - 1
            for s, i in self._open_slugs.items()
        }

    # ── Settings ──────────────────────────────────────────────────────────────

    def _open_settings(self) -> None:
        try:
            from nexus.ui.gui.settings_dialog import SettingsDialog
            dlg = SettingsDialog(self)
            dlg.exec()
        except Exception as exc:
            log.exception("Failed to open settings dialog")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Settings Error",
                                 f"Could not open Settings:\n\n{exc}\n\n"
                                 "Check the terminal for the full traceback.")

    # ── Add project ───────────────────────────────────────────────────────────

    def _add_project(self) -> None:
        dialog = _AddProjectDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return

        name, modules, desc = dialog.get_result()
        if not name:
            QMessageBox.warning(self, "Invalid name", "Project name cannot be empty.")
            return
        if not modules:
            QMessageBox.warning(self, "No modules", "Please select at least one module.")
            return

        try:
            create_project(name, modules, desc)
            log.info("Created project: %s (modules: %s)", name, modules)
        except ValueError as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self._grid.refresh()
        self.statusBar().showMessage(f"Project '{name}' created.")


def run_gui() -> None:
    from nexus.core.logger import setup as setup_logging
    from nexus.app import _register_skills
    setup_logging()
    _register_skills()

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Nexus")
    window = NexusGuiApp()
    window.show()
    sys.exit(app.exec())
