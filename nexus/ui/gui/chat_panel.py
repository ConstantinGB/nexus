from __future__ import annotations
import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QTextEdit, QLineEdit, QLabel, QSizePolicy,
)

from nexus.core.logger import get
from nexus.ui.gui.theme import ACCENT_G, ACCENT_P, TEXT_DIM, BG
from nexus.ui.gui.pty_terminal import PtyTerminalWidget

_ACCENT_CYAN = "#00D9FF"

log = get("ui.gui.chat_panel")

_ROOT         = Path(__file__).parent.parent.parent.parent
_PROJECTS_DIR = _ROOT / "projects"

_COMPRESS_THRESHOLD = 50
_COMPRESS_KEEP      = 40

_MODE_CLAUDE   = "chat"
_MODE_LOCAL    = "local"
_MODE_SHELL    = "shell"


# ── AI worker ─────────────────────────────────────────────────────────────────

class _AIWorker(QThread):
    response_ready = Signal(str)
    error_occurred = Signal(str)

    def __init__(
        self,
        messages: list,
        system_prompt: str,
        skill_scopes: list[str],
        force_provider: str = "",
        intent: dict | None = None,
    ) -> None:
        super().__init__()
        self._messages       = messages
        self._system_prompt  = system_prompt
        self._skill_scopes   = skill_scopes
        self._force_provider = force_provider
        self._intent         = intent

    def run(self) -> None:
        import asyncio
        try:
            from nexus.ai.client import AIClient
            client = AIClient(force_provider=self._force_provider)
            result = asyncio.run(client.chat(
                messages      = self._messages,
                system_prompt = self._system_prompt,
                skill_scopes  = self._skill_scopes,
                intent        = self._intent,
            ))
            self.response_ready.emit(result or "")
        except Exception as exc:
            log.exception("AIWorker failed")
            self.error_occurred.emit(str(exc))


# ── Local AI chat pane ────────────────────────────────────────────────────────

class _ChatPane(QWidget):
    def __init__(
        self,
        slug: str,
        module_key: str,
        skill_scopes: list[str],
        force_provider: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._slug           = slug
        self._module_key     = module_key
        self._skill_scopes   = skill_scopes
        self._force_provider = force_provider
        self._messages: list[dict] = []
        self._worker: _AIWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setPlaceholderText("Conversation will appear here…")
        layout.addWidget(self._log, 1)

        input_row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a message and press Enter…")
        self._input.returnPressed.connect(self._send)
        input_row.addWidget(self._input, 1)

        self._send_btn = QPushButton("Send")
        self._send_btn.setObjectName("primary")
        self._send_btn.clicked.connect(self._send)
        input_row.addWidget(self._send_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear)
        input_row.addWidget(clear_btn)

        layout.addLayout(input_row)

        self._status = QLabel("")
        self._status.setObjectName("dim")
        layout.addWidget(self._status)

    # ── Persistence ───────────────────────────────────────────────────────────

    def _history_path(self) -> Path:
        suffix = "local_history.json" if self._force_provider == "local" else "chat_history.json"
        return _PROJECTS_DIR / self._slug / suffix

    def load_history(self) -> None:
        try:
            data = json.loads(self._history_path().read_text())
            if isinstance(data, list):
                self._messages = data
                for msg in self._messages:
                    role    = msg.get("role", "")
                    content = msg.get("content", "")
                    if isinstance(content, str) and role in ("user", "assistant"):
                        self._append_bubble(role, content)
        except (FileNotFoundError, json.JSONDecodeError):
            self._messages = []

    def _save_history(self) -> None:
        if len(self._messages) > _COMPRESS_THRESHOLD:
            self._messages = self._messages[-_COMPRESS_KEEP:]
        try:
            path = self._history_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._messages, ensure_ascii=False, indent=2))
        except Exception:
            log.exception("Failed to save chat history for %s", self._slug)

    # ── Send ──────────────────────────────────────────────────────────────────

    def submit_message(self, text: str) -> None:
        self._input.setText(text)
        self._send()

    def _send(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        text = self._input.text().strip()
        if not text:
            return

        from nexus.core.config_manager import is_ai_configured
        if not is_ai_configured():
            self._append_info("AI not configured — open Nexus Settings to add an API key.")
            return

        self._input.clear()
        self._append_bubble("user", text)
        self._messages.append({"role": "user", "content": text})

        self._send_btn.setEnabled(False)
        self._status.setText("Thinking…")

        system_prompt = self._read_claude_md()
        from nexus.ai.intent_router import classify
        intent = classify(text, self._module_key)
        self._worker  = _AIWorker(
            list(self._messages), system_prompt,
            self._skill_scopes, self._force_provider, intent,
        )
        self._worker.response_ready.connect(self._on_response)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.finished.connect(self._on_done)
        self._worker.start()

    def _on_response(self, reply: str) -> None:
        if reply.strip():
            self._append_bubble("assistant", reply)
            self._messages.append({"role": "assistant", "content": reply})
            self._save_history()

    def _on_error(self, msg: str) -> None:
        self._append_info(f"Error: {msg}")
        if self._messages and self._messages[-1]["role"] == "user":
            self._messages.pop()

    def _on_done(self) -> None:
        self._send_btn.setEnabled(True)
        self._status.setText("")
        self._worker = None

    def _clear(self) -> None:
        self._messages = []
        self._log.clear()
        try:
            self._history_path().unlink(missing_ok=True)
        except Exception:
            pass

    # ── Display ───────────────────────────────────────────────────────────────

    def _append_bubble(self, role: str, text: str) -> None:
        colour = ACCENT_G if role == "user" else ACCENT_P
        prefix = "You" if role == "user" else "AI"
        escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self._log.append(
            f'<span style="color:{colour};font-weight:bold">[{prefix}]</span> '
            f'<span style="color:#E0D0FF">{escaped}</span>'
        )
        self._log.append("")

    def _append_info(self, text: str) -> None:
        self._log.append(
            f'<span style="color:{TEXT_DIM};font-style:italic">{text}</span>'
        )

    def _read_claude_md(self) -> str:
        try:
            return (_PROJECTS_DIR / self._slug / "CLAUDE.md").read_text(errors="replace")
        except FileNotFoundError:
            return ""


# ── Public ChatPanel ──────────────────────────────────────────────────────────

class ChatPanel(QWidget):
    """Three-mode panel: Claude CLI · Local AI · Shell.

    Claude and Shell tabs embed real PTY terminals (pyte-backed) so the user
    gets an interactive session with their .bashrc and the actual claude CLI
    rather than a read-only output log.
    """

    def __init__(
        self,
        slug:         str,
        module_key:   str,
        skill_scopes: list[str],
        parent:       QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._slug         = slug
        self._module_key   = module_key
        self._skill_scopes = skill_scopes
        self._build_ui()
        self._load_default_mode()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Toggle strip
        toggle = QHBoxLayout()
        toggle.setSpacing(4)

        self._btn_claude = QPushButton("Claude")
        self._btn_local  = QPushButton("Local AI")
        self._btn_shell  = QPushButton("Shell")

        for btn in (self._btn_claude, self._btn_local, self._btn_shell):
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            toggle.addWidget(btn)

        self._btn_claude.clicked.connect(lambda: self._set_mode(_MODE_CLAUDE))
        self._btn_local.clicked.connect(lambda: self._set_mode(_MODE_LOCAL))
        self._btn_shell.clicked.connect(lambda: self._set_mode(_MODE_SHELL))

        layout.addLayout(toggle)

        # Stacked content
        self._stack = QStackedWidget()

        project_dir = str(_PROJECTS_DIR / self._slug)

        # index 0 — Claude CLI terminal
        self._claude_term = PtyTerminalWidget("claude", cwd=project_dir)

        # index 1 — Local AI chat
        self._local_pane = _ChatPane(
            self._slug, self._module_key, self._skill_scopes, force_provider="local",
        )

        # index 2 — interactive bash shell
        self._shell_term = PtyTerminalWidget("bash -i", cwd=project_dir)

        self._stack.addWidget(self._claude_term)   # 0
        self._stack.addWidget(self._local_pane)    # 1
        self._stack.addWidget(self._shell_term)    # 2

        layout.addWidget(self._stack, 1)

    # ── Mode switching ────────────────────────────────────────────────────────

    _MODE_INDEX = {_MODE_CLAUDE: 0, _MODE_LOCAL: 1, _MODE_SHELL: 2}

    def _set_mode(self, mode: str) -> None:
        self._btn_claude.setChecked(mode == _MODE_CLAUDE)
        self._btn_local.setChecked(mode == _MODE_LOCAL)
        self._btn_shell.setChecked(mode == _MODE_SHELL)
        self._stack.setCurrentIndex(self._MODE_INDEX.get(mode, 0))

        # Lazy-start PTY terminals on first visit
        if mode == _MODE_CLAUDE:
            self._claude_term.start()
        elif mode == _MODE_LOCAL and not self._local_pane._messages:
            self._local_pane.load_history()
        elif mode == _MODE_SHELL:
            self._shell_term.start()

    def _load_default_mode(self) -> None:
        from nexus.core.config_manager import load_global_config
        default = load_global_config().get("ai", {}).get("default_panel", _MODE_CLAUDE)
        if default not in (_MODE_CLAUDE, _MODE_LOCAL, _MODE_SHELL):
            default = _MODE_CLAUDE
        self._set_mode(default)

    # ── Public API ────────────────────────────────────────────────────────────

    def submit_message(self, text: str) -> None:
        """Programmatically submit a message or command to the active pane.

        For the Claude CLI terminal, types the text followed by Enter.
        For Local AI, goes through the chat pane.
        """
        idx = self._stack.currentIndex()
        if idx == 0:
            # Claude CLI: type the prompt and press Enter
            self._claude_term.start()
            self._claude_term._write(text.encode("utf-8", errors="replace") + b"\r")
        elif idx == 1:
            self._local_pane.submit_message(text)
        # Shell: not applicable for programmatic messages

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._claude_term.stop()
        self._shell_term.stop()
        super().closeEvent(event)
