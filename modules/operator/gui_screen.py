from __future__ import annotations
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QTabWidget,
    QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton,
    QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
    QSplitter, QDialog, QDialogButtonBox, QDateEdit, QTimeEdit,
    QComboBox, QInputDialog, QMessageBox,
)

from nexus.core.project_manager import ProjectInfo
from nexus.ui.gui.base_project_window import BaseProjectWindow
from nexus.ui.gui.chat_panel import ChatPanel
from nexus.ui.gui.theme import ACCENT_G, ACCENT_M, ACCENT_P, TEXT_DIM, SURFACE

_PROJECTS_ROOT = Path(__file__).parent.parent.parent / "projects"


def _data_dir(slug: str, sub: str) -> Path:
    return _PROJECTS_ROOT / slug / "data" / sub


# ── Dialogs ───────────────────────────────────────────────────────────────────

class _AddEventDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Event")
        self.setMinimumWidth(340)
        layout = QVBoxLayout(self)
        form   = QFormLayout()

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


class _AddTaskDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Task")
        self.setMinimumWidth(320)
        layout = QVBoxLayout(self)
        form   = QFormLayout()

        self._title    = QLineEdit()
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


# ── Tab widgets ───────────────────────────────────────────────────────────────

class _CalendarTab(QWidget):
    def __init__(self, slug: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._slug = slug
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("+ Add Event")
        self._add_btn.clicked.connect(self._add_event)
        btn_row.addWidget(self._add_btn)

        self._del_btn = QPushButton("Delete")
        self._del_btn.clicked.connect(self._delete_event)
        btn_row.addWidget(self._del_btn)

        self._range_label = QLabel("Showing next 30 days")
        self._range_label.setObjectName("dim")
        btn_row.addStretch()
        btn_row.addWidget(self._range_label)
        layout.addLayout(btn_row)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Date", "Time", "Title", "Description"])
        self._tree.setColumnWidth(0, 110)
        self._tree.setColumnWidth(1, 60)
        self._tree.setColumnWidth(2, 200)
        layout.addWidget(self._tree, 1)

        self._empty_label = QLabel("No upcoming events.\nUse  + Add Event  to schedule something.")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setObjectName("dim")
        self._empty_label.hide()
        layout.addWidget(self._empty_label)

        self.refresh()

    def refresh(self) -> None:
        self._tree.clear()
        try:
            from modules.operator.calendar_module import CalendarData
            cal    = CalendarData(_data_dir(self._slug, "calendar"))
            today  = date.today()
            events = cal.get_upcoming(days=30)
            for e in sorted(events, key=lambda x: x["start"]):
                start = e["start"]
                d_str = start[:10]
                t_str = start[11:16] if len(start) > 10 else ""
                item  = QTreeWidgetItem([d_str, t_str, e["title"], e.get("description", "")])
                item.setData(0, Qt.UserRole, e["id"])
                self._tree.addTopLevelItem(item)
        except Exception as exc:
            item = QTreeWidgetItem(["Error", "", str(exc), ""])
            self._tree.addTopLevelItem(item)
        empty = self._tree.topLevelItemCount() == 0
        self._tree.setVisible(not empty)
        self._empty_label.setVisible(empty)

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
            from modules.operator.calendar_module import CalendarData
            cal = CalendarData(_data_dir(self._slug, "calendar"))
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
            from modules.operator.calendar_module import CalendarData
            cal = CalendarData(_data_dir(self._slug, "calendar"))
            cal.delete_event(event_id)
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))


class _NotesTab(QWidget):
    def __init__(self, slug: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._slug = slug
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Horizontal)

        # Left: note list + buttons
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        btn_row = QHBoxLayout()
        self._new_btn = QPushButton("+ New")
        self._new_btn.clicked.connect(self._new_note)
        btn_row.addWidget(self._new_btn)
        self._del_btn = QPushButton("Delete")
        self._del_btn.clicked.connect(self._delete_note)
        btn_row.addWidget(self._del_btn)
        left_layout.addLayout(btn_row)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_selection)
        left_layout.addWidget(self._list, 1)

        self._empty_label = QLabel("No notes yet.\nUse  + New  to create your first note.")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setObjectName("dim")
        self._empty_label.hide()
        left_layout.addWidget(self._empty_label)
        splitter.addWidget(left)

        # Right: content editor
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(self._save_note)
        right_layout.addWidget(self._save_btn)

        self._content = QTextEdit()
        self._content.setPlaceholderText("Note content (Markdown)")
        right_layout.addWidget(self._content, 1)
        splitter.addWidget(right)

        splitter.setSizes([260, 600])
        layout.addWidget(splitter, 1)

        self._notes: list[dict] = []
        self.refresh()

    def refresh(self) -> None:
        self._list.clear()
        self._notes = []
        try:
            from modules.operator.notes_module import NotesData
            nd = NotesData(_data_dir(self._slug, "notes"))
            self._notes = nd.notes
            for n in nd.notes:
                self._list.addItem(n["title"])
        except Exception as exc:
            self._list.addItem(f"[error: {exc}]")
        empty = self._list.count() == 0
        self._list.setVisible(not empty)
        self._empty_label.setVisible(empty)

    def _on_selection(self, row: int) -> None:
        if row < 0 or row >= len(self._notes):
            self._content.clear()
            return
        note = self._notes[row]
        try:
            from modules.operator.notes_module import NotesData
            nd      = NotesData(_data_dir(self._slug, "notes"))
            content = nd.get_content(note["id"])
            self._content.setPlainText(content)
        except Exception:
            pass

    def _save_note(self) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._notes):
            return
        note = self._notes[row]
        try:
            from modules.operator.notes_module import NotesData
            nd = NotesData(_data_dir(self._slug, "notes"))
            nd.update_note(note["id"], self._content.toPlainText())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _new_note(self) -> None:
        from nexus.ui.gui.theme import RETROWAVE_THEME
        title, ok = QInputDialog.getText(self, "New Note", "Note title:")
        if not ok or not title.strip():
            return
        try:
            from modules.operator.notes_module import NotesData
            nd = NotesData(_data_dir(self._slug, "notes"))
            nd.create_note(title.strip())
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _delete_note(self) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._notes):
            return
        note = self._notes[row]
        confirm = QMessageBox.question(
            self, "Delete note?",
            f"Delete '{note['title']}'? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            from modules.operator.notes_module import NotesData
            nd = NotesData(_data_dir(self._slug, "notes"))
            nd.delete_note(note["id"])
            self._content.clear()
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))


class _TasksTab(QWidget):
    _PRIORITY_COLOUR = {"high": ACCENT_M, "medium": ACCENT_G, "low": TEXT_DIM}

    def __init__(self, slug: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._slug = slug
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        btn_row = QHBoxLayout()
        self._add_btn      = QPushButton("+ Add Task")
        self._complete_btn = QPushButton("✓ Complete")
        self._del_btn      = QPushButton("Delete")
        self._add_btn.clicked.connect(self._add_task)
        self._complete_btn.clicked.connect(self._complete_task)
        self._del_btn.clicked.connect(self._delete_task)
        for btn in (self._add_btn, self._complete_btn, self._del_btn):
            btn_row.addWidget(btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Task", "Priority", "Deadline"])
        self._tree.setColumnWidth(0, 320)
        self._tree.setColumnWidth(1, 80)
        layout.addWidget(self._tree, 1)

        self._empty_label = QLabel("No tasks yet.\nUse  + Add Task  to get started.")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setObjectName("dim")
        self._empty_label.hide()
        layout.addWidget(self._empty_label)

        self.refresh()

    def refresh(self) -> None:
        self._tree.clear()
        try:
            from modules.operator.todo_module import TodoData
            td = TodoData(_data_dir(self._slug, "todo"))
            for lst in td.lists:
                list_item = QTreeWidgetItem([lst["name"], "", ""])
                list_item.setData(0, Qt.UserRole, ("list", lst["id"]))
                list_item.setExpanded(True)
                self._add_task_items(list_item, lst["tasks"])
                self._tree.addTopLevelItem(list_item)
        except Exception as exc:
            self._tree.addTopLevelItem(QTreeWidgetItem([f"Error: {exc}", "", ""]))
        empty = self._tree.topLevelItemCount() == 0
        self._tree.setVisible(not empty)
        self._empty_label.setVisible(empty)

    def _add_task_items(self, parent: QTreeWidgetItem, tasks: list) -> None:
        for t in tasks:
            title   = ("✓ " if t["completed"] else "") + t["title"]
            pri     = t.get("priority", "medium")
            dl      = (t.get("deadline") or "")[:10]
            item    = QTreeWidgetItem([title, pri, dl])
            colour  = self._PRIORITY_COLOUR.get(pri, TEXT_DIM)
            item.setForeground(1, QColor(colour))
            item.setData(0, Qt.UserRole, ("task", t["id"]))
            if t["completed"]:
                item.setForeground(0, QColor(TEXT_DIM))
            parent.addChild(item)
            if t.get("subtasks"):
                self._add_task_items(item, t["subtasks"])

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
            from modules.operator.todo_module import TodoData
            td  = TodoData(_data_dir(self._slug, "todo"))
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

    def _selected_task(self) -> tuple[str | None, str | None]:
        item = self._tree.currentItem()
        if not item:
            return None, None
        kind, id_ = item.data(0, Qt.UserRole) or (None, None)
        if kind != "task":
            return None, None
        return id_, None

    def _complete_task(self) -> None:
        task_id, _ = self._selected_task()
        if not task_id:
            return
        try:
            from modules.operator.todo_module import TodoData
            td       = TodoData(_data_dir(self._slug, "todo"))
            lst, _   = td.find_task(task_id)
            if lst:
                td.complete_task(lst["id"], task_id)
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _delete_task(self) -> None:
        task_id, _ = self._selected_task()
        if not task_id:
            return
        try:
            from modules.operator.todo_module import TodoData
            td     = TodoData(_data_dir(self._slug, "todo"))
            lst, _ = td.find_task(task_id)
            if lst:
                td.delete_task(lst["id"], task_id)
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))


# ── Main screen ───────────────────────────────────────────────────────────────

class GuiScreen(BaseProjectWindow):
    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"Operator — {project.name}")

        tabs = QTabWidget()
        self.setCentralWidget(tabs)

        self._chat = ChatPanel(
            slug         = project.slug,
            module_key   = "operator",
            skill_scopes = ["global", "operator"],
        )
        tabs.addTab(self._chat, "💬 Chat")

        self._calendar = _CalendarTab(project.slug)
        tabs.addTab(self._calendar, "📅 Calendar")

        self._notes = _NotesTab(project.slug)
        tabs.addTab(self._notes, "📝 Notes")

        self._tasks = _TasksTab(project.slug)
        tabs.addTab(self._tasks, "✓ Tasks")

        tabs.currentChanged.connect(self._on_tab_changed)

        self._build_toolbar()
        self._show_startup_summary()

    def _build_toolbar(self) -> None:
        from PySide6.QtWidgets import QToolBar
        tb = QToolBar("Operator", self)
        tb.setMovable(False)
        self.addToolBar(tb)

        brief_action = QAction("☀ Today's Brief", self)
        brief_action.triggered.connect(self._send_brief)
        tb.addAction(brief_action)

        refresh_action = QAction("⟳ Refresh", self)
        refresh_action.triggered.connect(self._refresh_all)
        tb.addAction(refresh_action)

    def _on_tab_changed(self, index: int) -> None:
        # Refresh data tabs when switched to
        tab = self.centralWidget().widget(index)
        if hasattr(tab, "refresh"):
            tab.refresh()

    def _show_startup_summary(self) -> None:
        """Populate the status bar with today's snapshot — no AI required."""
        slug  = self.project.slug
        today = date.today()
        parts: list[str] = [today.strftime("%A, %d %B %Y")]

        try:
            from modules.operator.calendar_module import CalendarData
            cal    = CalendarData(_data_dir(slug, "calendar"))
            events = cal.get_events_for_date(today)
            if events:
                parts.append(f"{len(events)} event(s) today")
            else:
                parts.append("no events today")
        except Exception:
            pass

        try:
            from modules.operator.todo_module import TodoData
            td      = TodoData(_data_dir(slug, "todo"))
            pending = td.get_pending()
            if pending:
                high = sum(1 for t in pending if t.get("priority") == "high")
                msg  = f"{len(pending)} pending task(s)"
                if high:
                    msg += f" ({high} high-priority)"
                parts.append(msg)
        except Exception:
            pass

        self.statusBar().showMessage("  ·  ".join(parts))

    def _send_brief(self) -> None:
        self.centralWidget().setCurrentIndex(0)
        today  = date.today().isoformat()
        slug   = self.project.slug
        prompt = (
            f"Good morning! Please give me a brief for today ({today}). "
            f"Check my calendar for today's events (project_slug='{slug}'), "
            f"list my pending tasks, and mention any recent notes if relevant."
        )
        self._chat.submit_message(prompt)

    def _refresh_all(self) -> None:
        self._calendar.refresh()
        self._notes.refresh()
        self._tasks.refresh()

    def closeEvent(self, event) -> None:
        if hasattr(self, "_chat"):
            self._chat.closeEvent(event)
        super().closeEvent(event)
