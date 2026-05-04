from __future__ import annotations

import shutil
from pathlib import Path
from nexus.core.project_manager import ProjectInfo
from nexus.ui.gui.module_base import ModuleGuiBase

log = __import__("nexus.core.logger", fromlist=["get"]).get("streaming.gui_screen")


class GuiScreen(ModuleGuiBase):
    SKILL_SCOPES = ["global", "streaming"]

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"Streaming — {project.name}")
        self._mod = self._cfg.get("streaming", {})
        self._populate()

    def _build_toolbar(self) -> None:
        self._add_btn("Launch OBS",   self._launch_obs,   primary=True)
        self._add_btn("Check Logs",   self._check_logs)
        self._add_btn("List Scenes",  self._list_scenes)
        self._add_btn("Open Config",  self._open_config)

    def _populate(self) -> None:
        m = self._mod
        config_dir = m.get("obs_config_dir", "")
        scenes = 0
        if config_dir:
            sc_dir = Path(config_dir).expanduser() / "basic" / "scenes"
            if sc_dir.is_dir():
                scenes = len(list(sc_dir.glob("*.json")))
        self._set_info([
            ("OBS config dir",    config_dir or "(not set)"),
            ("Scene collections", str(scenes)),
            ("OBS binary",        "✓" if shutil.which("obs") else "✗ not found"),
        ])

    # ── Actions ───────────────────────────────────────────────────────────────

    def _launch_obs(self) -> None:
        if not shutil.which("obs"):
            self._append("[error] obs not found in PATH.")
            return
        self._run_cmd(["obs"])

    def _check_logs(self) -> None:
        d = self._mod.get("obs_config_dir", "")
        if not d:
            self._append("[error] OBS config dir not set.")
            return
        log_dir = Path(d).expanduser() / "logs"
        if not log_dir.is_dir():
            self._append(f"[error] {log_dir} not found.")
            return
        logs = sorted(log_dir.glob("*.txt"), reverse=True)
        if not logs:
            self._append("[info] No log files found.")
            return
        self._append(f"[info] Latest log: {logs[0]}")
        self._append(logs[0].read_text()[-4000:])

    def _list_scenes(self) -> None:
        d = self._mod.get("obs_config_dir", "")
        if not d:
            self._append("[error] OBS config dir not set.")
            return
        sc_dir = Path(d).expanduser() / "basic" / "scenes"
        for f in sorted(sc_dir.glob("*.json")):
            self._append(f"  {f.stem}")

    def _open_config(self) -> None:
        d = self._mod.get("obs_config_dir", "")
        if d:
            from nexus.core.platform import launch
            launch(d)
