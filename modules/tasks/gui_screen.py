from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QMessageBox,
    QTreeWidget, QTreeWidgetItem, QDialog, QFormLayout,
    QLineEdit, QComboBox, QDialogButtonBox,
)

from nexus.core.project_manager import ProjectInfo
from nexus.core.config_manager import load_project_config
from nexus.ui.gui.base_project_window import BaseProjectWindow
from nexus.ui.gui.theme import ACCENT_G, ACCENT_M, TEXT_DIM

log = __import__("nexus.core.logger", fromlist=["get"]).get("tasks.gui_screen")

_PROJECTS_ROOT = Path(__file__).parent.parent.parent / "projects"

_PRIORITY_COLOUR = {"high": ACCENT_M, "medium": ACCENT_G, "low": TEXT_DIM}


def _data_dir(slug: str) -> Path:
    return _PROJECTS_ROOT / slug / "data" / "todo"


class _AddTaskDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Task")
        self.setMinimumWidth(320)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._title = QLineEdit()
        self._title.setPlaceholderText("Task title")
        form.addRow("Title:", self._title)

        self._list_name = QLineEdit()
        self._list_name.setPlaceholderText("Tasks (default)")
        form.addRow("List:", self._list_name)

        self._priority = QComboBox()
        for p in ("medium", "high", "low"):
            self._priority.addItem(p, userData=p)
        form.addRow("Priority:", self._priority)

        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_result(self) -> dict:
        return {
            "title":     self._title.text().strip(),
            "list_name": self._list_name.text().strip() or None,
            "priority":  self._priority.currentData(),
        }


class GuiScreen(BaseProjectWindow):
    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"Tasks — {project.name}")
        self._cfg = load_project_config(project.slug)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add Task")
        btn_add.clicked.connect(self._add_task)
        btn_row.addWidget(btn_add)
        btn_complete = QPushButton("Complete")
        btn_complete.clicked.connect(self._complete_task)
        btn_row.addWidget(btn_complete)
        btn_del = QPushButton("Delete")
        btn_del.clicked.connect(self._delete_task)
        btn_row.addWidget(btn_del)
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.refresh)
        btn_row.addWidget(btn_refresh)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Task", "Priority", "Deadline"])
        self._tree.setColumnWidth(0, 320)
        self._tree.setColumnWidth(1, 80)
        content_layout.addWidget(self._tree)
        layout.addWidget(content, 1)

        self.setCentralWidget(root)
        self.refresh()

    def refresh(self) -> None:
        self._tree.clear()
        try:
            from nexus.core.data.tasks import TodoData
            td = TodoData(_data_dir(self.project.slug))
            for lst in td.lists:
                list_item = QTreeWidgetItem([lst["name"], "", ""])
                list_item.setData(0, Qt.UserRole, ("list", lst["id"]))
                list_item.setExpanded(True)
                self._add_task_items(list_item, lst["tasks"])
                self._tree.addTopLevelItem(list_item)
        except Exception as exc:
            log.exception("Failed to refresh tasks")
            self._tree.addTopLevelItem(QTreeWidgetItem([f"Error: {exc}", "", ""]))

    def _add_task_items(self, parent: QTreeWidgetItem, tasks: list) -> None:
        for t in tasks:
            title = ("Done: " if t["completed"] else "") + t["title"]
            pri = t.get("priority", "medium")
            dl = (t.get("deadline") or "")[:10]
            item = QTreeWidgetItem([title, pri, dl])
            colour = _PRIORITY_COLOUR.get(pri, TEXT_DIM)
            item.setForeground(1, QColor(colour))
            item.setData(0, Qt.UserRole, ("task", t["id"]))
            if t["completed"]:
                item.setForeground(0, QColor(TEXT_DIM))
            parent.addChild(item)
            if t.get("subtasks"):
                self._add_task_items(item, t["subtasks"])

    def _selected_task_id(self) -> str | None:
        item = self._tree.currentItem()
        if not item:
            return None
        data = item.data(0, Qt.UserRole)
        if not data or data[0] != "task":
            return None
        return data[1]

    def _add_task(self) -> None:
        from nexus.ui.gui.theme import RETROWAVE_THEME
        dialog = _AddTaskDialog(self)
        dialog.setStyleSheet(RETROWAVE_THEME)
        if dialog.exec() != QDialog.Accepted:
            return
        result = dialog.get_result()
        if not result["title"]:
            return
        try:
            from nexus.core.data.tasks import TodoData
            td = TodoData(_data_dir(self.project.slug))
            lst = td.ensure_default_list()
            if result["list_name"]:
                named = td.get_list_by_name(result["list_name"])
                if named is None:
                    named = td.add_list(result["list_name"])
                lst = named
            td.add_task(lst["id"], result["title"], priority=result["priority"])
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _complete_task(self) -> None:
        task_id = self._selected_task_id()
        if not task_id:
            return
        try:
            from nexus.core.data.tasks import TodoData
            td = TodoData(_data_dir(self.project.slug))
            lst, _ = td.find_task(task_id)
            if lst:
                td.complete_task(lst["id"], task_id)
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _delete_task(self) -> None:
        task_id = self._selected_task_id()
        if not task_id:
            return
        try:
            from nexus.core.data.tasks import TodoData
            td = TodoData(_data_dir(self.project.slug))
            lst, _ = td.find_task(task_id)
            if lst:
                td.delete_task(lst["id"], task_id)
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

