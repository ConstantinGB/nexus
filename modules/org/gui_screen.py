from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import QListWidget, QInputDialog
from nexus.core.project_manager import ProjectInfo
from nexus.ui.gui.module_base import ModuleGuiBase

log = __import__("nexus.core.logger", fromlist=["get"]).get("org.gui_screen")


class GuiScreen(ModuleGuiBase):
    SKILL_SCOPES = ["global", "org"]

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"Org — {project.name}")
        self._mod = self._cfg.get("org", {})
        self._refresh()

    def _build_toolbar(self) -> None:
        self._add_btn("New Plan",      self._new_plan,     primary=True)
        self._add_btn("New Diagram",   self._new_diagram)
        self._add_btn("New Schedule",  self._new_schedule)
        self._add_btn("Open Dir",      self._open_dir)
        self._add_btn("↻ Refresh",     self._refresh)

    def _build_extra(self) -> None:
        self._file_list = QListWidget()
        self._file_list.setMinimumHeight(180)
        self._extra_layout.addWidget(self._file_list)

    def _refresh(self) -> None:
        self._mod = self._cfg.get("org", {})
        org_dir = self._mod.get("org_dir", "")
        files = []
        if org_dir:
            p = Path(org_dir).expanduser()
            if p.is_dir():
                files = sorted(p.glob("*.md")) + sorted(p.glob("*.mmd")) + sorted(p.glob("*.yaml"))
        self._file_list.clear()
        for f in files:
            self._file_list.addItem(f.name)
        self._set_info([
            ("Org dir",  org_dir or "(not set)"),
            ("Files",    str(len(files))),
        ])

    # ── Actions ───────────────────────────────────────────────────────────────

    def _new_file(self, prefix: str, suffix: str, template: str) -> None:
        org_dir = self._mod.get("org_dir", "")
        if not org_dir:
            self._append("[error] Org dir not configured.")
            return
        name, ok = QInputDialog.getText(self, f"New {prefix}", "Name:")
        if not ok or not name.strip():
            return
        path = Path(org_dir).expanduser() / f"{name.strip()}{suffix}"
        path.write_text(template.format(name=name.strip()))
        from nexus.core.platform import open_path
        open_path(str(path))
        self._refresh()

    def _new_plan(self) -> None:
        self._new_file("Plan", ".md", "# Plan: {name}\n\n## Goals\n\n## Steps\n\n## Notes\n")

    def _new_diagram(self) -> None:
        self._new_file("Diagram", ".mmd", "graph TD\n    A[{name}] --> B[...]\n")

    def _new_schedule(self) -> None:
        self._new_file("Schedule", ".md", "# Schedule: {name}\n\n| Task | Date | Done |\n|------|------|------|\n")

    def _open_dir(self) -> None:
        d = self._mod.get("org_dir", "")
        if d:
            from nexus.core.platform import open_path
            open_path(d)
