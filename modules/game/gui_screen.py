from __future__ import annotations

import shutil
from pathlib import Path
from nexus.core.project_manager import ProjectInfo
from nexus.ui.gui.module_base import ModuleGuiBase

log = __import__("nexus.core.logger", fromlist=["get"]).get("game.gui_screen")


class GuiScreen(ModuleGuiBase):
    SKILL_SCOPES = ["global", "game"]

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"Game — {project.name}")
        self._mod = self._cfg.get("game", {})
        self._populate()

    def _build_toolbar(self) -> None:
        self._add_btn("Launch Editor", self._launch_editor, primary=True)
        self._add_btn("Run Game",      self._run_game)
        self._add_btn("Lint",          self._do_lint)
        self._add_btn("Export…",       self._do_export)

    def _populate(self) -> None:
        m = self._mod
        proj_dir = m.get("project_dir", "")
        scene_count = 0
        if proj_dir:
            p = Path(proj_dir).expanduser()
            if p.is_dir():
                scene_count = len(list(p.glob("**/*.tscn")))
        self._set_info([
            ("Project dir",    proj_dir or "(not set)"),
            ("Engine",         m.get("engine", "godot")),
            ("Scene count",    str(scene_count)),
            ("Godot binary",   "✓" if shutil.which("godot") else "✗ not found"),
        ])

    # ── Actions ───────────────────────────────────────────────────────────────

    def _launch_editor(self) -> None:
        proj_dir = self._mod.get("project_dir", "")
        if not shutil.which("godot"):
            self._append("[error] godot not found in PATH.")
            return
        cmd = ["godot", "--editor"]
        if proj_dir:
            cmd.append(str(Path(proj_dir).expanduser() / "project.godot"))
        self._run_cmd(cmd)

    def _run_game(self) -> None:
        proj_dir = self._mod.get("project_dir", "")
        if not shutil.which("godot"):
            self._append("[error] godot not found in PATH.")
            return
        self._run_cmd(["godot"], cwd=proj_dir or None)

    def _do_lint(self) -> None:
        proj_dir = self._mod.get("project_dir", "")
        if shutil.which("gdtoolkit"):
            self._run_cmd(["gdtoolkit", "gdlint", "."], cwd=proj_dir or None)
        else:
            self._append("[error] gdtoolkit not found — install with: pip install gdtoolkit")

    def _do_export(self) -> None:
        self._not_implemented("Export dialog")
