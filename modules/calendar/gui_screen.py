from __future__ import annotations
from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QTextEdit, QMessageBox,
    QTreeWidget, QTreeWidgetItem, QDialog, QFormLayout,
    QLineEdit, QDialogButtonBox, QDateEdit, QTimeEdit,
)
from PySide6.QtCore import QDate

from nexus.core.project_manager import ProjectInfo
from nexus.core.config_manager import load_project_config
from nexus.ui.gui.base_project_window import BaseProjectWindow
from nexus.ui.gui.chat_panel import ChatPanel

log = __import__("nexus.core.logger", fromlist=["get"]).get("calendar.gui_screen")

_PROJECTS_ROOT = Path(__file__).parent.parent.parent / "projects"


def _data_dir(slug: str) -> Path:
    return _PROJECTS_ROOT / slug / "data" / "calendar"


class _AddEventDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Event")
        self.setMinimumWidth(340)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._title = QLineEdit()
        self._title.setPlaceholderText("Team sync")
        form.addRow("Title:", self._title)

        self._date = QDateEdit(QDate.currentDate())
        self._date.setCalendarPopup(True)
        self._date.setDisplayFormat("yyyy-MM-dd")
        form.addRow("Date:", self._date)

        self._time = QTimeEdit()
        self._time.setDisplayFormat("HH:mm")
        form.addRow("Time:", self._time)

        self._desc = QLineEdit()
        self._desc.setPlaceholderText("Optional description")
        form.addRow("Description:", self._desc)

        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_result(self) -> dict:
        d = self._date.date()
        t = self._time.time()
        return {
            "title":       self._title.text().strip(),
            "date":        f"{d.year():04d}-{d.month():02d}-{d.day():02d}",
            "time":        f"{t.hour():02d}:{t.minute():02d}",
            "description": self._desc.text().strip(),
        }


class GuiScreen(BaseProjectWindow):
    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"Calendar — {project.name}")
        self._cfg = load_project_config(project.slug)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        # Toolbar
        toolbar = QHBoxLayout()
        btn_add = QPushButton("+ Add Event")
        btn_add.clicked.connect(self._add_event)
        toolbar.addWidget(btn_add)
        btn_del = QPushButton("Delete Event")
        btn_del.clicked.connect(self._delete_event)
        toolbar.addWidget(btn_del)
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.refresh)
        toolbar.addWidget(btn_refresh)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Content
        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Date", "Time", "Title", "Description"])
        self._tree.setColumnWidth(0, 110)
        self._tree.setColumnWidth(1, 60)
        self._tree.setColumnWidth(2, 200)
        left_layout.addWidget(self._tree)
        splitter.addWidget(left)

        self._chat = ChatPanel(
            self.project.slug,
            "calendar",
            ["global", "calendar"],
            parent=self,
        )
        splitter.addWidget(self._chat)
        splitter.setSizes([600, 400])
        layout.addWidget(splitter, 1)

        self.setCentralWidget(root)
        self.refresh()

    def refresh(self) -> None:
        self._tree.clear()
        try:
            from nexus.core.data.calendar import CalendarData
            cal = CalendarData(_data_dir(self.project.slug))
            events = cal.get_upcoming(days=30)
            for e in sorted(events, key=lambda x: x["start"]):
                start = e["start"]
                d_str = start[:10]
                t_str = start[11:16] if len(start) > 10 else ""
                item = QTreeWidgetItem([d_str, t_str, e["title"], e.get("description", "")])
                item.setData(0, Qt.UserRole, e["id"])
                self._tree.addTopLevelItem(item)
        except Exception as exc:
            log.exception("Failed to refresh calendar")
            self._tree.addTopLevelItem(QTreeWidgetItem(["Error", "", str(exc), ""]))

    def _add_event(self) -> None:
        from nexus.ui.gui.theme import RETROWAVE_THEME
        dialog = _AddEventDialog(self)
        dialog.setStyleSheet(RETROWAVE_THEME)
        if dialog.exec() != QDialog.Accepted:
            return
        result = dialog.get_result()
        if not result["title"]:
            return
        try:
            from nexus.core.data.calendar import CalendarData
            cal = CalendarData(_data_dir(self.project.slug))
            cal.add_event(
                title=result["title"],
                start=f"{result['date']}T{result['time']}:00",
                description=result["description"],
            )
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _delete_event(self) -> None:
        item = self._tree.currentItem()
        if not item:
            return
        event_id = item.data(0, Qt.UserRole)
        if not event_id:
            return
        try:
            from nexus.core.data.calendar import CalendarData
            cal = CalendarData(_data_dir(self.project.slug))
            cal.delete_event(event_id)
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def closeEvent(self, event) -> None:
        if hasattr(self, "_chat"):
            self._chat.closeEvent(event)
        super().closeEvent(event)
