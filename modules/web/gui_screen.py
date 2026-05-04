from __future__ import annotations

from pathlib import Path
from nexus.core.project_manager import ProjectInfo
from nexus.ui.gui.module_base import ModuleGuiBase

log = __import__("nexus.core.logger", fromlist=["get"]).get("web.gui_screen")


class GuiScreen(ModuleGuiBase):
    SKILL_SCOPES = ["global", "web"]

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"Web — {project.name}")
        self._mod = self._cfg.get("web", {})
        self._proc_worker = None
        self._populate()

    def _build_toolbar(self) -> None:
        self._add_btn("Dev",        self._do_dev,     primary=True)
        self._add_btn("Build",      self._do_build)
        self._add_btn("Test",       self._do_test)
        self._add_btn("Lint",       self._do_lint)
        self._add_btn("Install",    self._do_install)
        self._add_btn("Run Script…",self._do_script)
        self._btn_stop = self._add_btn("■ Stop", self._do_stop)
        self._btn_stop.setEnabled(False)
        self._add_btn("Open Dir",   self._do_open)

    def _populate(self) -> None:
        m = self._mod
        scripts = m.get("scripts", {})
        self._set_info([
            ("Project dir",     m.get("project_dir", "")),
            ("Package manager", m.get("package_manager", "npm")),
            ("Scripts",         ", ".join(scripts.keys()) if scripts else "(none)"),
        ])

    def _pm(self) -> str:
        return self._mod.get("package_manager", "npm")

    def _cwd(self) -> str | None:
        d = self._mod.get("project_dir", "")
        return d or None

    def _run_pm(self, *args: str) -> None:
        self._proc_worker = self._run_cmd([self._pm()] + list(args), cwd=self._cwd())
        self._btn_stop.setEnabled(True)
        self._proc_worker.finished.connect(lambda: self._btn_stop.setEnabled(False))

    # ── Actions ───────────────────────────────────────────────────────────────

    def _do_dev(self) -> None:
        self._run_pm("run", "dev")

    def _do_build(self) -> None:
        self._run_pm("run", "build")

    def _do_test(self) -> None:
        self._run_pm("run", "test")

    def _do_lint(self) -> None:
        self._run_pm("run", "lint")

    def _do_install(self) -> None:
        self._run_pm("install")

    def _do_script(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        scripts = list(self._mod.get("scripts", {}).keys())
        if not scripts:
            self._not_implemented("No scripts configured")
            return
        script, ok = QInputDialog.getItem(self, "Run Script", "Script:", scripts, 0, False)
        if ok and script:
            self._run_pm("run", script)

    def _do_stop(self) -> None:
        if self._proc_worker and self._proc_worker.isRunning():
            self._proc_worker.terminate()
        self._btn_stop.setEnabled(False)

    def _do_open(self) -> None:
        d = self._mod.get("project_dir", "")
        if d:
            from nexus.core.platform import launch
            launch(d)
