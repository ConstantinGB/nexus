from __future__ import annotations
import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QListWidget, QTextEdit, QLabel,
    QInputDialog, QMessageBox,
)

from nexus.core.project_manager import ProjectInfo
from nexus.core.config_manager import load_project_config
from nexus.ui.gui.base_project_window import BaseProjectWindow
from nexus.ui.gui.chat_panel import ChatPanel


def _note_title(path: Path) -> str:
    try:
        text = path.read_text(errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
            m = re.match(r'^topic:\s*(.+)', line)
            if m:
                return m.group(1).strip()
    except Exception:
        pass
    return path.stem.replace("-", " ").title()


class GuiScreen(BaseProjectWindow):
    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"Research — {project.name}")

        cfg       = load_project_config(project.slug)
        notes_dir = cfg.get("research", {}).get("notes_dir", "")
        self._notes_dir = Path(notes_dir).expanduser() if notes_dir else None
        self._notes: list[Path] = []

        splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(splitter)

        # Left: note list + controls
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(8, 8, 4, 8)

        btn_row = QHBoxLayout()
        new_btn = QPushButton("+ New Note")
        new_btn.clicked.connect(self._new_note)
        btn_row.addWidget(new_btn)
        del_btn = QPushButton("Delete")
        del_btn.clicked.connect(self._delete_note)
        btn_row.addWidget(del_btn)
        ll.addLayout(btn_row)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_selection)
        ll.addWidget(QLabel("Notes:"))
        ll.addWidget(self._list, 1)
        splitter.addWidget(left)

        # Right: content editor + chat
        right = QSplitter(Qt.Vertical)

        editor_pane = QWidget()
        el = QVBoxLayout(editor_pane)
        el.setContentsMargins(4, 8, 8, 4)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_note)
        el.addWidget(save_btn)
        self._editor = QTextEdit()
        self._editor.setPlaceholderText("Note content (Markdown)")
        el.addWidget(self._editor, 1)
        right.addWidget(editor_pane)

        self._chat = ChatPanel(
            slug         = project.slug,
            module_key   = "research",
            skill_scopes = ["global", "research"],
        )
        right.addWidget(self._chat)
        right.setSizes([400, 260])

        splitter.addWidget(right)
        splitter.setSizes([240, 720])

        self._load_notes()

    def _load_notes(self) -> None:
        self._list.clear()
        self._notes = []
        if not self._notes_dir or not self._notes_dir.exists():
            self._list.addItem("(notes_dir not configured or not found)")
            return
        files = sorted(
            [f for f in self._notes_dir.glob("*.md") if f.name != "CLAUDE.md"],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        self._notes = files
        for f in files:
            self._list.addItem(_note_title(f))

    def _on_selection(self, row: int) -> None:
        if row < 0 or row >= len(self._notes):
            self._editor.clear()
            return
        try:
            self._editor.setPlainText(self._notes[row].read_text(errors="replace"))
        except Exception:
            self._editor.clear()

    def _save_note(self) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._notes):
            return
        try:
            self._notes[row].write_text(self._editor.toPlainText(), encoding="utf-8")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _new_note(self) -> None:
        if not self._notes_dir:
            QMessageBox.warning(self, "Not configured", "Configure notes_dir in project settings first.")
            return
        title, ok = QInputDialog.getText(self, "New Note", "Note title:")
        if not ok or not title.strip():
            return
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "note"
        from datetime import date
        filename = f"{date.today().isoformat()}-{slug}.md"
        path = self._notes_dir / filename
        template = (
            f"---\ntitle: {title}\ndate: {date.today().isoformat()}\ntopic: {title}\ntags: []\n---\n\n"
        )
        try:
            path.write_text(template, encoding="utf-8")
            self._load_notes()
            idx = next((i for i, p in enumerate(self._notes) if p == path), 0)
            self._list.setCurrentRow(idx)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _delete_note(self) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._notes):
            return
        path = self._notes[row]
        confirm = QMessageBox.question(
            self, "Delete?", f"Delete '{path.name}'? Cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            path.unlink()
            self._editor.clear()
            self._load_notes()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def closeEvent(self, event) -> None:
        if hasattr(self, "_chat"):
            self._chat.closeEvent(event)
        super().closeEvent(event)
