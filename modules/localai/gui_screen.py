from __future__ import annotations

from PySide6.QtWidgets import QTextEdit, QLabel, QLineEdit, QHBoxLayout
from nexus.core.project_manager import ProjectInfo
from nexus.ui.gui.module_base import ModuleGuiBase

log = __import__("nexus.core.logger", fromlist=["get"]).get("localai.gui_screen")


class GuiScreen(ModuleGuiBase):
    SKILL_SCOPES = ["global", "localai"]

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"LocalAI — {project.name}")
        self._mod = self._cfg.get("localai", {})
        self._populate()

    def _build_toolbar(self) -> None:
        self._add_btn("▶ Run Inference", self._do_run,       primary=True)
        self._add_btn("Test Endpoint",   self._do_test)
        self._add_btn("Browse Models",   self._do_models)
        self._add_btn("Docker",          self._do_docker)

    def _build_extra(self) -> None:
        lbl = QLabel("Prompt:")
        lbl.setObjectName("subtitle")
        self._extra_layout.addWidget(lbl)
        self._prompt = QTextEdit()
        self._prompt.setPlaceholderText("Enter prompt…")
        self._prompt.setMinimumHeight(80)
        self._extra_layout.addWidget(self._prompt)

    def _populate(self) -> None:
        m = self._mod
        self._set_info([
            ("Endpoint", m.get("endpoint", "")),
            ("Model",    m.get("model", "")),
        ])

    # ── Actions ───────────────────────────────────────────────────────────────

    def _do_run(self) -> None:
        endpoint = self._mod.get("endpoint", "")
        model    = self._mod.get("model", "")
        prompt   = self._prompt.toPlainText().strip()
        if not endpoint or not model:
            self._append("[error] Endpoint and model must be configured.")
            return
        if not prompt:
            self._append("[warn] Enter a prompt first.")
            return
        import json, os
        payload = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}]})
        env = os.environ.copy()
        env["NEXUS_PROMPT"] = prompt
        self._run_cmd([
            "curl", "-s", "-X", "POST",
            f"{endpoint.rstrip('/')}/chat/completions",
            "-H", "Content-Type: application/json",
            "-d", payload,
        ])

    def _do_test(self) -> None:
        endpoint = self._mod.get("endpoint", "")
        if not endpoint:
            self._append("[error] Endpoint not configured.")
            return
        self._run_cmd(["curl", "-s", f"{endpoint.rstrip('/')}/models"])

    def _do_models(self) -> None:
        self._do_test()

    def _do_docker(self) -> None:
        self._run_cmd(["docker", "ps", "--filter", "name=localai"])
