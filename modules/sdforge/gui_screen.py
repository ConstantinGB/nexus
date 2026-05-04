from __future__ import annotations

from PySide6.QtWidgets import QLabel, QLineEdit, QHBoxLayout, QSpinBox
from nexus.core.project_manager import ProjectInfo
from nexus.ui.gui.module_base import ModuleGuiBase

log = __import__("nexus.core.logger", fromlist=["get"]).get("sdforge.gui_screen")


class GuiScreen(ModuleGuiBase):
    SKILL_SCOPES = ["global", "sdforge"]

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"SDForge — {project.name}")
        self._mod = self._cfg.get("sdforge", {})
        self._populate()

    def _build_toolbar(self) -> None:
        self._add_btn("▶ Start Server", self._start_server,  primary=True)
        self._add_btn("■ Stop Server",  self._stop_server)
        self._add_btn("Open Web UI",    self._open_webui)
        self._add_btn("Test Endpoint",  self._test_endpoint)
        self._add_btn("Browse Models",  self._browse_models)
        self._add_btn("Docker",         self._do_docker)
        self._add_btn("Generate",       self._do_generate)

    def _build_extra(self) -> None:
        row = QHBoxLayout()
        row.addWidget(QLabel("Positive prompt:"))
        self._extra_layout.addLayout(row)

        from PySide6.QtWidgets import QTextEdit
        self._prompt_pos = QTextEdit()
        self._prompt_pos.setPlaceholderText("a beautiful landscape, masterpiece…")
        self._prompt_pos.setMinimumHeight(60)
        self._extra_layout.addWidget(self._prompt_pos)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Negative:"))
        self._prompt_neg = QLineEdit()
        self._prompt_neg.setPlaceholderText("blurry, watermark…")
        row2.addWidget(self._prompt_neg)
        row2.addWidget(QLabel("Steps:"))
        self._steps = QSpinBox()
        self._steps.setRange(1, 150)
        self._steps.setValue(20)
        row2.addWidget(self._steps)
        self._extra_layout.addLayout(row2)

    def _populate(self) -> None:
        m = self._mod
        self._set_info([
            ("Endpoint", m.get("endpoint", "")),
            ("Model",    m.get("model", "")),
            ("Sampler",  m.get("sampler", "euler_a")),
        ])

    # ── Actions ───────────────────────────────────────────────────────────────

    def _start_server(self) -> None:
        self._not_implemented("Start SDForge server")

    def _stop_server(self) -> None:
        self._not_implemented("Stop SDForge server")

    def _open_webui(self) -> None:
        url = self._mod.get("endpoint", "")
        if url:
            import webbrowser
            webbrowser.open(url)
        else:
            self._append("[error] Endpoint not configured.")

    def _test_endpoint(self) -> None:
        endpoint = self._mod.get("endpoint", "")
        if not endpoint:
            self._append("[error] Endpoint not configured.")
            return
        self._run_cmd(["curl", "-s", f"{endpoint.rstrip('/')}/sdapi/v1/sd-models"])

    def _browse_models(self) -> None:
        self._test_endpoint()

    def _do_docker(self) -> None:
        self._run_cmd(["docker", "ps", "--filter", "name=sdforge"])

    def _do_generate(self) -> None:
        self._not_implemented("txt2img generation")
