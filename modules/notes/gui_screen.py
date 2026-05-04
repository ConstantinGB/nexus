from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QTextEdit, QMessageBox,
    QListWidget, QListWidgetItem, QInputDialog,
)

from nexus.core.project_manager import ProjectInfo
from nexus.core.config_manager import load_project_config
from nexus.ui.gui.base_project_window import BaseProjectWindow
from nexus.ui.gui.chat_panel import ChatPanel

log = __import__("nexus.core.logger", fromlist=["get"]).get("notes.gui_screen")

_PROJECTS_ROOT = Path(__file__).parent.parent.parent / "projects"


def _data_dir(slug: str) -> Path:
    return _PROJECTS_ROOT / slug / "data" / "notes"


class GuiScreen(BaseProjectWindow):
    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"Notes — {project.name}")
        self._cfg = load_project_config(project.slug)
        self._notes: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Horizontal)

        # Left: note list + buttons
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        btn_row = QHBoxLayout()
        btn_new = QPushButton("+ New")
        btn_new.clicked.connect(self._new_note)
        btn_row.addWidget(btn_new)
        btn_del = QPushButton("Delete")
        btn_del.clicked.connect(self._delete_note)
        btn_row.addWidget(btn_del)
        left_layout.addLayout(btn_row)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_selection)
        left_layout.addWidget(self._list, 1)
        splitter.addWidget(left)

        # Right: editor
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_note)
        right_layout.addWidget(save_btn)

        self._content = QTextEdit()
        self._content.setPlaceholderText("Note content (Markdown)")
        right_layout.addWidget(self._content, 1)
        splitter.addWidget(right)

        splitter.setSizes([260, 600])

        chat_split = QSplitter(Qt.Horizontal)
        chat_split.addWidget(splitter)
        self._chat = ChatPanel(
            self.project.slug,
            "notes",
            ["global", "notes"],
            parent=self,
        )
        chat_split.addWidget(self._chat)
        chat_split.setSizes([800, 400])
        layout.addWidget(chat_split, 1)

        self.setCentralWidget(root)
        self.refresh()

    def refresh(self) -> None:
        self._list.clear()
        self._notes = []
        try:
            from nexus.core.data.notes import NotesData
            nd = NotesData(_data_dir(self.project.slug))
            self._notes = nd.notes
            for n in nd.notes:
                self._list.addItem(n["title"])
        except Exception as exc:
            log.exception("Failed to refresh notes")
            self._list.addItem(f"[error: {exc}]")

    def _on_selection(self, row: int) -> None:
        if row < 0 or row >= len(self._notes):
            self._content.clear()
            return
        note = self._notes[row]
        try:
            from nexus.core.data.notes import NotesData
            nd = NotesData(_data_dir(self.project.slug))
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
            from nexus.core.data.notes import NotesData
            nd = NotesData(_data_dir(self.project.slug))
            nd.update_note(note["id"], self._content.toPlainText())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _new_note(self) -> None:
        from nexus.ui.gui.theme import RETROWAVE_THEME
        title, ok = QInputDialog.getText(self, "New Note", "Note title:")
        if not ok or not title.strip():
            return
        try:
            from nexus.core.data.notes import NotesData
            nd = NotesData(_data_dir(self.project.slug))
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
            from nexus.core.data.notes import NotesData
            nd = NotesData(_data_dir(self.project.slug))
            nd.delete_note(note["id"])
            self._content.clear()
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def closeEvent(self, event) -> None:
        if hasattr(self, "_chat"):
            self._chat.closeEvent(event)
        super().closeEvent(event)
