from __future__ import annotations

from PySide6.QtWidgets import QTextEdit, QLabel, QPushButton, QMessageBox
from nexus.core.project_manager import ProjectInfo
from nexus.ui.gui.module_base import ModuleGuiBase

log = __import__("nexus.core.logger", fromlist=["get"]).get("promptopt.gui_screen")

_SYSTEM_PROMPTS = {
    "text": (
        "You are an expert prompt engineer. Rewrite the user's prompt to be clearer, "
        "more specific, and more effective for a general-purpose language model. "
        "Return only the improved prompt — no explanation, no preamble."
    ),
    "instruct": (
        "You are an expert prompt engineer specialising in instruction-following models. "
        "Rewrite the user's prompt as a precise, unambiguous instruction set. "
        "Return only the improved prompt — no explanation, no preamble."
    ),
    "image": (
        "You are an expert prompt engineer specialising in image generation (Stable Diffusion, "
        "FLUX, Midjourney). Rewrite the user's prompt to be rich in visual detail, style, "
        "lighting, and composition cues. Use comma-separated tag style where appropriate. "
        "Return only the improved prompt — no explanation, no preamble."
    ),
}


class GuiScreen(ModuleGuiBase):
    SKILL_SCOPES = ["global", "promptopt"]

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"Prompt Opt — {project.name}")
        self._mod = self._cfg.get("promptopt", {})
        self._current_mode = self._mod.get("mode", "text")
        self._opt_worker = None
        self._populate()

    def _build_toolbar(self) -> None:
        self._btn_text     = self._add_btn("Text",     lambda: self._set_mode("text"),     primary=True)
        self._btn_instruct = self._add_btn("Instruct", lambda: self._set_mode("instruct"))
        self._btn_image    = self._add_btn("Image",    lambda: self._set_mode("image"))
        self._opt_btn      = self._add_btn("Optimize", self._do_optimize)
        self._add_btn("Copy",     self._do_copy)
        self._add_btn("Save",     self._do_save)

    def _build_extra(self) -> None:
        lbl = QLabel("Prompt:")
        lbl.setObjectName("subtitle")
        self._extra_layout.addWidget(lbl)
        self._prompt_input = QTextEdit()
        self._prompt_input.setPlaceholderText("Enter your prompt here…")
        self._prompt_input.setMinimumHeight(80)
        self._extra_layout.addWidget(self._prompt_input)

    def _populate(self) -> None:
        self._set_info([
            ("Mode",     self._current_mode),
            ("Save dir", self._mod.get("save_dir", "")),
        ])

    def _set_mode(self, mode: str) -> None:
        self._current_mode = mode
        self._append(f"[mode] switched to {mode}")
        self._populate()

    # ── Actions ───────────────────────────────────────────────────────────────

    def _do_optimize(self) -> None:
        prompt = self._prompt_input.toPlainText().strip()
        if not prompt:
            QMessageBox.information(self, "Empty prompt", "Enter a prompt to optimize.")
            return

        from nexus.core.config_manager import is_ai_configured
        if not is_ai_configured():
            QMessageBox.warning(self, "AI not configured",
                                "Open Nexus Settings and configure an AI provider first.")
            return

        if self._opt_worker and self._opt_worker.isRunning():
            return

        from nexus.ui.gui.chat_panel import _AIWorker
        system_prompt = _SYSTEM_PROMPTS.get(self._current_mode, _SYSTEM_PROMPTS["text"])
        messages = [{"role": "user", "content": f"Optimize the following {self._current_mode} prompt:\n\n{prompt}"}]

        self._opt_btn.setEnabled(False)
        self._append(f"[optimize] running {self._current_mode} optimization…")

        self._opt_worker = _AIWorker(messages, system_prompt, self._skill_scopes)
        self._opt_worker.response_ready.connect(self._on_optimized)
        self._opt_worker.error_occurred.connect(self._on_opt_error)
        self._opt_worker.finished.connect(self._on_opt_done)
        self._opt_worker.start()

    def _on_optimized(self, result: str) -> None:
        if result.strip():
            self._prompt_input.setPlainText(result.strip())
            self._append("[optimize] done — prompt updated above.")

    def _on_opt_error(self, msg: str) -> None:
        self._append(f"[optimize] error: {msg}")

    def _on_opt_done(self) -> None:
        self._opt_btn.setEnabled(True)
        self._opt_worker = None

    def _do_copy(self) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._prompt_input.toPlainText())
        self._append("[copied] prompt copied to clipboard.")

    def _do_save(self) -> None:
        save_dir = self._mod.get("save_dir", "")
        if not save_dir:
            QMessageBox.information(self, "No save dir",
                                    "Set a save_dir in project config first.")
            return
        from pathlib import Path
        import datetime
        dest = Path(save_dir).expanduser()
        dest.mkdir(parents=True, exist_ok=True)
        ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = dest / f"prompt_{self._current_mode}_{ts}.txt"
        path.write_text(self._prompt_input.toPlainText())
        self._append(f"[saved] {path}")
