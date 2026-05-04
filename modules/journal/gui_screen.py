from __future__ import annotations

import shutil
from pathlib import Path
from PySide6.QtWidgets import QListWidget, QInputDialog
from nexus.core.project_manager import ProjectInfo
from nexus.ui.gui.module_base import ModuleGuiBase

log = __import__("nexus.core.logger", fromlist=["get"]).get("journal.gui_screen")


class GuiScreen(ModuleGuiBase):
    SKILL_SCOPES = ["global", "journal"]

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"Journal — {project.name}")
        self._mod = self._cfg.get("journal", {})
        self._refresh()

    def _build_toolbar(self) -> None:
        self._add_btn("New Entry", self._new_entry,  primary=True)
        self._add_btn("Compile",   self._do_compile)
        self._add_btn("Open PDF",  self._open_pdf)
        self._add_btn("↻ Refresh", self._refresh)

    def _build_extra(self) -> None:
        self._entry_list = QListWidget()
        self._entry_list.setMinimumHeight(180)
        self._extra_layout.addWidget(self._entry_list)

    def _refresh(self) -> None:
        self._mod = self._cfg.get("journal", {})
        journal_dir = self._mod.get("journal_dir", "")
        entries = []
        if journal_dir:
            p = Path(journal_dir).expanduser()
            if p.is_dir():
                entries = sorted(p.glob("*.md"), reverse=True)
        self._entry_list.clear()
        for e in entries:
            self._entry_list.addItem(e.stem)
        self._set_info([
            ("Journal dir", journal_dir or "(not set)"),
            ("Entries",     str(len(entries))),
        ])

    # ── Actions ───────────────────────────────────────────────────────────────

    def _new_entry(self) -> None:
        journal_dir = self._mod.get("journal_dir", "")
        if not journal_dir:
            self._append("[error] Journal dir not configured.")
            return
        from datetime import date
        title = date.today().isoformat()
        path = Path(journal_dir).expanduser() / f"{title}.md"
        if not path.exists():
            path.write_text(f"# {title}\n\n")
        from nexus.core.platform import open_path
        open_path(str(path))
        self._refresh()

    def _do_compile(self) -> None:
        journal_dir = self._mod.get("journal_dir", "")
        if not journal_dir:
            self._append("[error] Journal dir not configured.")
            return
        if not shutil.which("pandoc"):
            self._append("[error] pandoc not found — install it first.")
            return
        out = str(Path(journal_dir).expanduser() / "journal.pdf")
        sources = sorted(str(f) for f in Path(journal_dir).expanduser().glob("*.md"))
        if not sources:
            self._append("[info] No entries to compile.")
            return
        self._run_cmd(["pandoc"] + sources + ["-o", out])

    def _open_pdf(self) -> None:
        journal_dir = self._mod.get("journal_dir", "")
        if not journal_dir:
            self._append("[error] Journal dir not configured.")
            return
        pdf = Path(journal_dir).expanduser() / "journal.pdf"
        if not pdf.exists():
            self._append("[info] PDF not found — compile first.")
            return
        from nexus.core.platform import open_path
        open_path(str(pdf))
