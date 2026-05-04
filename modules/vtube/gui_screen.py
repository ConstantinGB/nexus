from __future__ import annotations

import shutil
from nexus.core.project_manager import ProjectInfo
from nexus.ui.gui.module_base import ModuleGuiBase

log = __import__("nexus.core.logger", fromlist=["get"]).get("vtube.gui_screen")


class GuiScreen(ModuleGuiBase):
    SKILL_SCOPES = ["global", "vtube"]

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"VTube — {project.name}")
        self._mod = self._cfg.get("vtube", {})
        self._populate()

    def _build_toolbar(self) -> None:
        self._add_btn("Launch Runtime",  self._launch_runtime,  primary=True)
        self._add_btn("Start Tracker",   self._start_tracker)
        self._add_btn("Check Camera",    self._check_camera)
        self._add_btn("Open Model Dir",  self._open_model_dir)

    def _populate(self) -> None:
        m = self._mod
        runtime = m.get("runtime", "")
        self._set_info([
            ("Runtime",      runtime or "(not set)"),
            ("Tracker port", str(m.get("tracker_port", 21412))),
            ("Model dir",    m.get("model_dir", "")),
        ])

    # ── Actions ───────────────────────────────────────────────────────────────

    def _launch_runtime(self) -> None:
        runtime = self._mod.get("runtime", "")
        if not runtime:
            self._append("[error] Runtime not configured.")
            return
        self._run_cmd([runtime])

    def _start_tracker(self) -> None:
        self._not_implemented("VTube tracker start")

    def _check_camera(self) -> None:
        self._run_cmd(["v4l2-ctl", "--list-devices"] if shutil.which("v4l2-ctl")
                      else ["ls", "/dev/video*"])

    def _open_model_dir(self) -> None:
        d = self._mod.get("model_dir", "")
        if d:
            from nexus.core.platform import launch
            launch(d)
        else:
            self._append("[info] Model dir not configured.")
