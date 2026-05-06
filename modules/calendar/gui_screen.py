from __future__ import annotations
from datetime import datetime

from PySide6.QtCore import Qt, QDate, QDateTime, QTime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QMessageBox,
    QListWidget, QListWidgetItem, QDialog, QFormLayout,
    QLineEdit, QDialogButtonBox, QDateEdit, QTimeEdit,
    QComboBox, QCheckBox, QCalendarWidget, QSplitter,
)

from nexus.core.project_manager import ProjectInfo
from nexus.core.config_manager import load_project_config
from nexus.ui.gui.base_project_window import BaseProjectWindow

log = __import__("nexus.core.logger", fromlist=["get"]).get("calendar.gui_screen")


def _get_calendar(project: ProjectInfo):
    from nexus.core.config_manager import get_module_mode
    from nexus.core.data.calendar import get_global_calendar, get_project_calendar
    mode = get_module_mode(load_project_config(project.slug), "calendar")
    return get_global_calendar() if mode == "integrated" else get_project_calendar(project.slug)


# ── Event dialog ──────────────────────────────────────────────────────────────

class _EventDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, event: dict | None = None) -> None:
        super().__init__(parent)
        self._event = event
        self.setWindowTitle("Edit Event" if event else "Add Event")
        self.setModal(True)
        self.setMinimumWidth(400)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        form   = QFormLayout()

        self._title = QLineEdit()
        self._title.setPlaceholderText("Team sync")
        if self._event:
            self._title.setText(self._event.get("title", ""))
        form.addRow("Title:", self._title)

        self._start_date = QDateEdit(QDate.currentDate())
        self._start_date.setCalendarPopup(True)
        self._start_date.setDisplayFormat("yyyy-MM-dd")
        if self._event:
            dt = QDateTime.fromString(self._event["start"], Qt.ISODate)
            if dt.isValid():
                self._start_date.setDate(dt.date())
        form.addRow("Start date:", self._start_date)

        self._start_time = QTimeEdit(QTime(9, 0))
        self._start_time.setDisplayFormat("HH:mm")
        if self._event:
            dt = QDateTime.fromString(self._event["start"], Qt.ISODate)
            if dt.isValid():
                self._start_time.setTime(dt.time())
        form.addRow("Start time:", self._start_time)

        self._has_end = QCheckBox("Set end time")
        if self._event and self._event.get("end") and self._event["end"] != self._event["start"]:
            self._has_end.setChecked(True)
        self._has_end.toggled.connect(self._toggle_end)
        form.addRow("", self._has_end)

        self._end_date_lbl = QLabel("End date:")
        self._end_date     = QDateEdit(QDate.currentDate())
        self._end_date.setCalendarPopup(True)
        self._end_date.setDisplayFormat("yyyy-MM-dd")
        self._end_time_lbl = QLabel("End time:")
        self._end_time     = QTimeEdit(QTime(10, 0))
        self._end_time.setDisplayFormat("HH:mm")
        if self._event and self._event.get("end"):
            edt = QDateTime.fromString(self._event["end"], Qt.ISODate)
            if edt.isValid():
                self._end_date.setDate(edt.date())
                self._end_time.setTime(edt.time())
        form.addRow(self._end_date_lbl, self._end_date)
        form.addRow(self._end_time_lbl, self._end_time)

        self._recurrence = QComboBox()
        self._recurrence.addItems(["None", "Daily", "Weekly", "Monthly", "Yearly"])
        if self._event and self._event.get("recurrence"):
            rec_type = self._event["recurrence"].get("type", "").capitalize()
            idx = self._recurrence.findText(rec_type)
            if idx >= 0:
                self._recurrence.setCurrentIndex(idx)
        form.addRow("Recurrence:", self._recurrence)

        self._location = QLineEdit()
        self._location.setPlaceholderText("optional")
        if self._event:
            self._location.setText(self._event.get("location", ""))
        form.addRow("Location:", self._location)

        self._desc = QTextEdit()
        self._desc.setMaximumHeight(80)
        self._desc.setPlaceholderText("optional description")
        if self._event:
            self._desc.setPlainText(self._event.get("description", ""))
        form.addRow("Description:", self._desc)

        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._toggle_end(self._has_end.isChecked())

    def _toggle_end(self, visible: bool) -> None:
        for w in (self._end_date_lbl, self._end_date, self._end_time_lbl, self._end_time):
            w.setVisible(visible)

    def get_result(self) -> dict:
        start_dt = QDateTime(self._start_date.date(), self._start_time.time())
        end_str  = None
        if self._has_end.isChecked():
            end_dt  = QDateTime(self._end_date.date(), self._end_time.time())
            end_str = end_dt.toString(Qt.ISODate)
        recurrence = None
        rec_text   = self._recurrence.currentText()
        if rec_text != "None":
            recurrence = {"type": rec_text.lower(), "interval": 1, "until": None}
        return {
            "title":       self._title.text().strip(),
            "start":       start_dt.toString(Qt.ISODate),
            "end":         end_str,
            "location":    self._location.text().strip(),
            "description": self._desc.toPlainText().strip(),
            "recurrence":  recurrence,
        }


# ── Main GUI screen ───────────────────────────────────────────────────────────

class GuiScreen(BaseProjectWindow):
    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"Calendar — {project.name}")
        self._selected_event_id: str | None = None
        self._build_ui()
        self._refresh_for_date(self._cal_widget.selectedDate())

    def _build_ui(self) -> None:
        root   = QWidget()
        layout = QVBoxLayout(root)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        # Mode indicator
        from nexus.core.config_manager import get_module_mode
        mode   = get_module_mode(load_project_config(self.project.slug), "calendar")
        source = "Global calendar (Integrated)" if mode == "integrated" \
            else f"Project calendar (Standalone — {self.project.slug})"
        mode_lbl = QLabel(f"  {source}")
        mode_lbl.setObjectName("dim")
        layout.addWidget(mode_lbl)

        # Action toolbar
        toolbar      = QHBoxLayout()
        add_btn      = QPushButton("+ Add Event")
        edit_btn     = QPushButton("Edit Selected")
        del_btn      = QPushButton("Delete Selected")
        upcoming_btn = QPushButton("Next 7 Days")
        add_btn.clicked.connect(self._add_event)
        edit_btn.clicked.connect(self._edit_event)
        del_btn.clicked.connect(self._delete_event)
        upcoming_btn.clicked.connect(self._show_upcoming)
        for b in (add_btn, edit_btn, del_btn, upcoming_btn):
            toolbar.addWidget(b)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Calendar + event list
        splitter = QSplitter(Qt.Vertical)
        self._cal_widget = QCalendarWidget()
        self._cal_widget.clicked.connect(self._refresh_for_date)
        splitter.addWidget(self._cal_widget)

        self._event_list = QListWidget()
        self._event_list.itemClicked.connect(self._on_item_clicked)
        splitter.addWidget(self._event_list)
        splitter.setSizes([320, 200])
        layout.addWidget(splitter)

        self.setCentralWidget(root)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _fmt_dt(iso: str) -> str:
        try:
            return datetime.fromisoformat(iso).strftime("%d %b  %H:%M")
        except Exception:
            return iso

    def _refresh_for_date(self, qdate: QDate) -> None:
        self._event_list.clear()
        self._selected_event_id = None
        date_str = qdate.toString("yyyy-MM-dd")
        try:
            cal    = _get_calendar(self.project)
            events = cal.get_events_for_date(qdate.toPython())
        except Exception as exc:
            self._event_list.addItem(f"Error: {exc}")
            return

        if not events:
            item = QListWidgetItem(f"No events on {date_str}")
            item.setFlags(Qt.NoItemFlags)
            self._event_list.addItem(item)
            return

        for e in sorted(events, key=lambda x: x["start"]):
            rec_tag  = " ↻" if e.get("recurrence") else ""
            end_part = f"  →  {self._fmt_dt(e['end'])}" if e.get("end") and e["end"] != e["start"] else ""
            loc_part = f"  📍 {e['location']}" if e.get("location") else ""
            item     = QListWidgetItem(
                f"{self._fmt_dt(e['start'])}{end_part}{rec_tag}\n  {e['title']}{loc_part}"
            )
            item.setData(Qt.UserRole, e["id"])
            self._event_list.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        self._selected_event_id = item.data(Qt.UserRole)

    # ── CRUD actions ──────────────────────────────────────────────────────────

    def _add_event(self) -> None:
        dlg = _EventDialog(self)
        if not dlg.exec():
            return
        data = dlg.get_result()
        if not data["title"]:
            QMessageBox.warning(self, "Missing title", "Please enter an event title.")
            return
        try:
            _get_calendar(self.project).add_event(**data)
            self._refresh_for_date(self._cal_widget.selectedDate())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            log.exception("add_event failed")

    def _edit_event(self) -> None:
        if not self._selected_event_id:
            QMessageBox.information(self, "No selection", "Click an event to select it first.")
            return
        try:
            cal   = _get_calendar(self.project)
            event = next((e for e in cal.events if e["id"] == self._selected_event_id), None)
            if event is None:
                QMessageBox.warning(self, "Not found", "Event not found.")
                return
            dlg = _EventDialog(self, event)
            if not dlg.exec():
                return
            data = dlg.get_result()
            cal.update_event(self._selected_event_id, **data)
            self._refresh_for_date(self._cal_widget.selectedDate())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            log.exception("edit_event failed")

    def _delete_event(self) -> None:
        if not self._selected_event_id:
            QMessageBox.information(self, "No selection", "Click an event to select it first.")
            return
        reply = QMessageBox.question(
            self, "Delete event", "Delete the selected event?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            _get_calendar(self.project).delete_event(self._selected_event_id)
            self._selected_event_id = None
            self._refresh_for_date(self._cal_widget.selectedDate())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            log.exception("delete_event failed")

    def _show_upcoming(self) -> None:
        self._event_list.clear()
        self._selected_event_id = None
        try:
            events = _get_calendar(self.project).get_upcoming(days=7)
        except Exception as exc:
            self._event_list.addItem(f"Error: {exc}")
            return
        if not events:
            item = QListWidgetItem("No events in the next 7 days.")
            item.setFlags(Qt.NoItemFlags)
            self._event_list.addItem(item)
            return
        for e in sorted(events, key=lambda x: x["start"]):
            rec_tag = " ↻" if e.get("recurrence") else ""
            item    = QListWidgetItem(
                f"{self._fmt_dt(e['start'])}{rec_tag}\n  {e['title']}"
            )
            item.setData(Qt.UserRole, e["id"])
            self._event_list.addItem(item)
