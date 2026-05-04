from __future__ import annotations

import shutil
from pathlib import Path
from PySide6.QtWidgets import QListWidget
from nexus.core.project_manager import ProjectInfo
from nexus.ui.gui.module_base import ModuleGuiBase

log = __import__("nexus.core.logger", fromlist=["get"]).get("emulator.gui_screen")


class GuiScreen(ModuleGuiBase):
    SKILL_SCOPES = ["global", "emulator"]

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"Emulator — {project.name}")
        self._mod = self._cfg.get("emulator", {})
        self._refresh()

    def _build_toolbar(self) -> None:
        self._add_btn("Launch RetroArch", self._launch_ra,      primary=True)
        self._add_btn("Browse by System", self._browse_system)
        self._add_btn("Open ROM Dir",     self._open_rom_dir)

    def _build_extra(self) -> None:
        self._system_list = QListWidget()
        self._system_list.setMinimumHeight(160)
        self._extra_layout.addWidget(self._system_list)

    def _refresh(self) -> None:
        self._mod = self._cfg.get("emulator", {})
        rom_dir = self._mod.get("rom_dir", "")
        systems = []
        if rom_dir:
            p = Path(rom_dir).expanduser()
            if p.is_dir():
                systems = [d.name for d in sorted(p.iterdir()) if d.is_dir()]
        self._system_list.clear()
        for s in systems:
            self._system_list.addItem(s)
        self._set_info([
            ("ROM dir",     rom_dir or "(not set)"),
            ("Systems",     str(len(systems))),
            ("RetroArch",   "✓" if shutil.which("retroarch") else "✗ not found"),
        ])

    # ── Actions ───────────────────────────────────────────────────────────────

    def _launch_ra(self) -> None:
        if not shutil.which("retroarch"):
            self._append("[error] retroarch not found in PATH.")
            return
        self._run_cmd(["retroarch"])

    def _browse_system(self) -> None:
        sel = self._system_list.currentItem()
        if not sel:
            self._append("[info] Select a system from the list first.")
            return
        from nexus.core.platform import open_path
        rom_dir = self._mod.get("rom_dir", "")
        if rom_dir:
            open_path(str(Path(rom_dir).expanduser() / sel.text()))

    def _open_rom_dir(self) -> None:
        d = self._mod.get("rom_dir", "")
        if d:
            from nexus.core.platform import open_path
            open_path(d)
