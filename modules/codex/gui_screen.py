from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QTextBrowser, QTreeWidget, QTreeWidgetItem,
    QDialog, QListWidget, QListWidgetItem, QDialogButtonBox, QMessageBox,
)

from nexus.core.project_manager import ProjectInfo

log = __import__("nexus.core.logger", fromlist=["get"]).get("codex.gui_screen")


def _get_codex_sources(project: ProjectInfo) -> dict[str, list[Path]]:
    from nexus.core.config_manager import load_project_config
    cfg    = load_project_config(project.slug)
    active = set(project.modules)
    result: dict[str, list[Path]] = {}

    if "journal" in active:
        jdir_str = cfg.get("journal", {}).get("journal_dir", "")
        jdir = Path(jdir_str).expanduser() if jdir_str else project.path / "journal"
        result["journal"] = sorted(jdir.rglob("*.tex")) if jdir.is_dir() else []

    if "notes" in active:
        ndir = project.path / "data" / "notes"
        result["notes"] = sorted(ndir.glob("*.md")) if ndir.is_dir() else []

    if "research" in active:
        rdir_str = cfg.get("research", {}).get("notes_dir", "")
        rdir = Path(rdir_str).expanduser() if rdir_str else project.path / "notes"
        result["research"] = sorted(rdir.rglob("*.md")) if rdir.is_dir() else []

    if "org" in active:
        odir_str = cfg.get("org", {}).get("output_dir", "")
        odir = Path(odir_str).expanduser() if odir_str else project.path / "plans"
        result["org"] = sorted(odir.rglob("*.md")) if odir.is_dir() else []

    if "youtube" in active:
        ydir_str = cfg.get("youtube", {}).get("output_dir", "")
        if ydir_str:
            ydir = Path(ydir_str).expanduser()
            result["youtube"] = sorted(
                f for f in ydir.rglob("*") if f.suffix in {".txt", ".md"}
            ) if ydir.is_dir() else []

    return result


class _PandocWorker(QThread):
    finished_ok  = Signal(str)   # path to PDF
    finished_err = Signal(str)   # error message

    def __init__(self, cmd: list[str], out_pdf: str, parent=None) -> None:
        super().__init__(parent)
        self._cmd = cmd
        self._out_pdf = out_pdf

    def run(self) -> None:
        try:
            result = subprocess.run(
                self._cmd,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                self.finished_ok.emit(self._out_pdf)
            else:
                self.finished_err.emit(result.stdout + result.stderr)
        except FileNotFoundError:
            self.finished_err.emit("pandoc not found. Install pandoc and xelatex.")
        except Exception as exc:
            self.finished_err.emit(str(exc))


class _ReorderDialog(QDialog):
    """Show checked files in a list; user can reorder with Up/Down before export."""

    def __init__(self, files: list[Path], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Order Files for PDF")
        self.setMinimumSize(480, 420)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Drag or use buttons to set the order:"))
        self._list = QListWidget()
        self._list.setDragDropMode(QListWidget.InternalMove)
        for f in files:
            item = QListWidgetItem(f.name)
            item.setData(Qt.UserRole, str(f))
            self._list.addItem(item)
        layout.addWidget(self._list)

        arrow_row = QHBoxLayout()
        up_btn = QPushButton("↑ Up")
        dn_btn = QPushButton("↓ Down")
        up_btn.clicked.connect(self._move_up)
        dn_btn.clicked.connect(self._move_down)
        arrow_row.addWidget(up_btn)
        arrow_row.addWidget(dn_btn)
        arrow_row.addStretch()
        layout.addLayout(arrow_row)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _move_up(self) -> None:
        row = self._list.currentRow()
        if row <= 0:
            return
        item = self._list.takeItem(row)
        self._list.insertItem(row - 1, item)
        self._list.setCurrentRow(row - 1)

    def _move_down(self) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= self._list.count() - 1:
            return
        item = self._list.takeItem(row)
        self._list.insertItem(row + 1, item)
        self._list.setCurrentRow(row + 1)

    def ordered_paths(self) -> list[Path]:
        return [
            Path(self._list.item(i).data(Qt.UserRole))
            for i in range(self._list.count())
        ]


class GuiScreen(QWidget):
    """Codex: document explorer and PDF compiler."""

    SKILL_SCOPES = ["global", "codex"]

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(parent)
        self.project = project
        self._sources: dict[str, list[Path]] = {}
        self._worker: _PandocWorker | None = None
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(8, 8, 8, 8)

        # Toolbar
        toolbar = QHBoxLayout()
        self._btn_pdf = QPushButton("To PDF")
        self._btn_pdf.setObjectName("primary")
        self._btn_pdf.clicked.connect(self._start_export)
        refresh_btn = QPushButton("↻ Refresh")
        refresh_btn.clicked.connect(self._refresh)
        self._count_lbl = QLabel("0 checked")
        toolbar.addWidget(self._btn_pdf)
        toolbar.addWidget(refresh_btn)
        toolbar.addStretch()
        toolbar.addWidget(self._count_lbl)
        root.addLayout(toolbar)

        # Main splitter: file tree | preview
        splitter = QSplitter(Qt.Horizontal)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.itemChanged.connect(self._on_check_changed)
        self._tree.itemClicked.connect(self._on_item_clicked)
        splitter.addWidget(self._tree)

        self._preview = QTextBrowser()
        self._preview.setReadOnly(True)
        self._preview.setOpenExternalLinks(False)
        splitter.addWidget(self._preview)
        splitter.setSizes([280, 600])

        root.addWidget(splitter, 1)

    def _refresh(self) -> None:
        self._sources = _get_codex_sources(self.project)
        self._tree.blockSignals(True)
        self._tree.clear()
        for source_id, files in self._sources.items():
            if not files:
                continue
            parent = QTreeWidgetItem(self._tree, [source_id.title()])
            parent.setFlags(parent.flags() & ~Qt.ItemIsUserCheckable)
            parent.setExpanded(True)
            for f in files:
                child = QTreeWidgetItem(parent, [f.name])
                child.setData(0, Qt.UserRole, str(f))
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setCheckState(0, Qt.Unchecked)
        self._tree.blockSignals(False)
        self._update_count()

    def _on_check_changed(self, item: QTreeWidgetItem, col: int) -> None:
        self._update_count()

    def _on_item_clicked(self, item: QTreeWidgetItem, col: int) -> None:
        path_str = item.data(0, Qt.UserRole)
        if not path_str:
            return
        p = Path(path_str)
        try:
            text = p.read_text(errors="replace")
        except Exception:
            text = f"(Could not read {p.name})"
        self._preview.setPlainText(text)

    def _update_count(self) -> None:
        n = self._checked_paths().__len__()
        self._count_lbl.setText(f"{n} checked")

    def _checked_paths(self) -> list[Path]:
        paths = []
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            parent = root.child(i)
            for j in range(parent.childCount()):
                child = parent.child(j)
                if child.checkState(0) == Qt.Checked:
                    p = child.data(0, Qt.UserRole)
                    if p:
                        paths.append(Path(p))
        return paths

    def _start_export(self) -> None:
        files = self._checked_paths()
        if not files:
            QMessageBox.information(self, "Nothing selected", "Check at least one file.")
            return
        if not shutil.which("pandoc"):
            QMessageBox.warning(self, "pandoc not found",
                                "Install pandoc and xelatex to use PDF export.")
            return

        dlg = _ReorderDialog(files, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        ordered = dlg.ordered_paths()

        out_dir = self.project.path / "codex"
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_pdf = out_dir / f"codex_{ts}.pdf"

        cmd = ["pandoc"] + [str(f) for f in ordered] + [
            "-o", str(out_pdf),
            "--pdf-engine=xelatex",
        ]

        self._btn_pdf.setEnabled(False)
        self._btn_pdf.setText("Generating…")
        self._worker = _PandocWorker(cmd, str(out_pdf), parent=self)
        self._worker.finished_ok.connect(self._on_pdf_ok)
        self._worker.finished_err.connect(self._on_pdf_err)
        self._worker.start()

    def _on_pdf_ok(self, path: str) -> None:
        self._btn_pdf.setEnabled(True)
        self._btn_pdf.setText("To PDF")
        QMessageBox.information(self, "PDF ready", f"Saved to:\n{path}")

    def _on_pdf_err(self, msg: str) -> None:
        self._btn_pdf.setEnabled(True)
        self._btn_pdf.setText("To PDF")
        log.error("pandoc error: %s", msg)
        QMessageBox.warning(self, "PDF generation failed", msg[:400])
