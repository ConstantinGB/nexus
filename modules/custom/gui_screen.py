from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import QTextEdit, QLabel
from nexus.core.project_manager import ProjectInfo
from nexus.ui.gui.module_base import ModuleGuiBase

log = __import__("nexus.core.logger", fromlist=["get"]).get("custom.gui_screen")

_ROOT = Path(__file__).parent.parent.parent


class GuiScreen(ModuleGuiBase):
    SKILL_SCOPES = ["global", "custom"]

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"Custom — {project.name}")
        self._mod = self._cfg.get("custom", {})
        self._populate()

    def _build_toolbar(self) -> None:
        # self._cfg is set by ModuleGuiBase.__init__ before _build_toolbar is called
        mod = self._cfg.get("custom", {})
        cmds = mod.get("commands", [])
        for i, cmd in enumerate(cmds):
            label = cmd.get("label", f"Cmd {i+1}")
            self._add_btn(label, lambda c=cmd: self._run_cmd_entry(c), primary=(i == 0))
        self._add_btn("Open Folder", self._do_open)
        self._add_btn("↻ Reload",    self._populate)

    def _build_extra(self) -> None:
        lbl = QLabel("CLAUDE.md")
        lbl.setObjectName("subtitle")
        self._extra_layout.addWidget(lbl)
        self._context_view = QTextEdit()
        self._context_view.setReadOnly(True)
        self._context_view.setMinimumHeight(140)
        self._extra_layout.addWidget(self._context_view)

    def _populate(self) -> None:
        self._mod = self._cfg.get("custom", {})
        cmds = self._mod.get("commands", [])
        proj_dir = self._mod.get("project_dir", "")
        self._set_info([
            ("Project dir", proj_dir or "(not set)"),
            ("Commands",    str(len(cmds))),
        ])
        claude_md = _ROOT / "projects" / self.project.slug / "CLAUDE.md"
        if claude_md.exists():
            self._context_view.setPlainText(claude_md.read_text())
        else:
            self._context_view.setPlainText("(no CLAUDE.md found)")

    # ── Actions ───────────────────────────────────────────────────────────────

    def _run_cmd_entry(self, cmd: dict) -> None:
        shell_cmd = cmd.get("command", "")
        cwd = self._mod.get("project_dir") or None
        if not shell_cmd:
            return
        import shlex
        self._run_cmd(shlex.split(shell_cmd), cwd=cwd)

    def _do_open(self) -> None:
        d = self._mod.get("project_dir", "")
        if d:
            from nexus.core.platform import launch
            launch(d)
