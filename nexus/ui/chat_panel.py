from __future__ import annotations
import json
from pathlib import Path

from textual.app import ComposeResult
from textual.css.query import NoMatches
from textual.events import Key
from textual.message import Message
from textual.widgets import Label, Button, RichLog, TextArea
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get

log = get("ui.chat_panel")

_ROOT         = Path(__file__).parent.parent.parent
_PROJECTS_DIR = _ROOT / "projects"
_MODULES_DIR  = _ROOT / "modules"

_COMPRESS_THRESHOLD = 50
_COMPRESS_KEEP      = 40


class _ChatTextArea(TextArea):
    """TextArea that sends on Enter; Shift+Enter inserts a newline."""

    class Submit(Message):
        """Posted when the user presses Enter to send."""

    def _on_key(self, event: Key) -> None:
        if event.key == "enter":
            event.prevent_default()
            self.post_message(_ChatTextArea.Submit())
        elif event.key == "shift+enter":
            event.prevent_default()
            self.insert("\n")


class ChatPanel(Vertical):
    """Toggleable AI chat panel, mounted inside any BaseProjectScreen."""

    DEFAULT_CSS = """
    ChatPanel .pane-title {
        color: #00FF88; text-style: bold; height: 1;
        background: #2D1B4E; padding: 0 1;
    }
    ChatPanel #chat-log   { height: 1fr; background: #0A0518; }
    ChatPanel #chat-input { height: 5; border: solid #3A2260; }
    ChatPanel #chat-btns  { height: 3; padding: 0 1; }
    ChatPanel #chat-btns Button { min-width: 8; margin-right: 1; }
    """

    def __init__(
        self,
        project_slug: str,
        module_key: str,
        skill_scopes: list[str],
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._slug        = project_slug
        self._module_key  = module_key
        self._scopes      = skill_scopes
        self._messages:   list[dict] = []
        self._busy        = False

    # ── Compose ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Label("💬 AI Chat", classes="pane-title")
        yield RichLog(id="chat-log", auto_scroll=True, wrap=True, markup=False)
        yield _ChatTextArea("", id="chat-input")
        with Horizontal(id="chat-btns"):
            yield Button("Send",  id="chat-send", variant="primary")
            yield Button("/init", id="chat-init")
            yield Button("Clear", id="chat-clear")

    def on_mount(self) -> None:
        self._load_history()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _history_path(self) -> Path:
        return _PROJECTS_DIR / self._slug / "chat_history.json"

    def _load_history(self) -> None:
        try:
            data = json.loads(self._history_path().read_text())
            if isinstance(data, list):
                self._messages = data
                chat_log = self.query_one("#chat-log", RichLog)
                for msg in self._messages:
                    role    = msg.get("role", "")
                    content = msg.get("content", "")
                    if isinstance(content, str) and role in ("user", "assistant"):
                        prefix = "You" if role == "user" else "AI"
                        chat_log.write(f"[{prefix}] {content}")
        except (FileNotFoundError, json.JSONDecodeError, Exception):
            self._messages = []

    def _save_history(self) -> None:
        self._compress_if_needed()
        try:
            path = self._history_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._messages, ensure_ascii=False, indent=2))
        except Exception:
            log.exception("Failed to save chat history for %s", self._slug)

    def _compress_if_needed(self) -> None:
        if len(self._messages) > _COMPRESS_THRESHOLD:
            self._messages = self._messages[-_COMPRESS_KEEP:]

    # ── Button handler ────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        event.stop()
        if bid == "chat-send":
            self.run_worker(self._send())
        elif bid == "chat-init":
            self._start_init()
        elif bid == "chat-clear":
            self._confirm_clear()

    def on__chat_text_area_submit(self, _: _ChatTextArea.Submit) -> None:
        self.run_worker(self._send())

    # ── Send ──────────────────────────────────────────────────────────────────

    async def _send(self) -> None:
        if self._busy:
            return
        ta   = self.query_one("#chat-input", _ChatTextArea)
        text = ta.text.strip()
        if not text:
            return

        chat_log = self.query_one("#chat-log", RichLog)
        ta.load_text("")
        chat_log.write(f"[You] {text}")
        self._messages.append({"role": "user", "content": text})

        from nexus.core.config_manager import is_ai_configured
        if not is_ai_configured():
            chat_log.write(
                "[info] AI not configured — open Settings (s) to add a key or local model."
            )
            self._messages.pop()
            return

        self._busy = True
        self.query_one("#chat-send", Button).disabled = True

        system_prompt = self._read_claude_md()
        reply: str | None = None
        try:
            from nexus.ai.client import AIClient
            client = AIClient()
            reply  = await client.chat(
                messages      = self._messages,
                system_prompt = system_prompt,
                skill_scopes  = self._scopes,
            )
        except Exception:
            log.exception("Chat send failed for %s", self._slug)
            chat_log.write("[error] AI request failed — see log.")
            self._messages.pop()
        finally:
            self._busy = False
            try:
                self.query_one("#chat-send", Button).disabled = False
            except NoMatches:
                pass

        if reply is not None:
            chat_log.write(f"[AI] {reply}")
            self._messages.append({"role": "assistant", "content": reply})
            self._save_history()

    # ── /init ─────────────────────────────────────────────────────────────────

    def _start_init(self) -> None:
        from nexus.ui.base_project_screen import InputModal
        self.app.push_screen(
            InputModal(
                "/init — Personalize AI context",
                "Describe this project's purpose, key tools, and connected projects:",
                placeholder="e.g. My Godot platformer — uses GDScript, notes in my Codex project",
            ),
            self._run_init,
        )

    def _run_init(self, description: str | None) -> None:
        if not description:
            return
        self.run_worker(self._do_init(description))

    async def _do_init(self, description: str) -> None:
        chat_log = self.query_one("#chat-log", RichLog)

        from nexus.core.config_manager import is_ai_configured
        if not is_ai_configured():
            chat_log.write(
                "[info] AI not configured — open Settings (s) to add a key or local model."
            )
            return

        chat_log.write("[/init] Reading project context…")

        current_md    = self._read_claude_md()
        template      = self._read_template()
        project_cfg   = self._read_project_config()
        peers         = self._list_peers()

        init_system = (
            "You are a project context writer for Nexus, a personal project manager. "
            "Your task is to write a CLAUDE.md file that will serve as the AI system prompt "
            "for this project. Combine static module knowledge from the template with the "
            "user's specific setup details.\n\n"
            "Write ONLY the CLAUDE.md content — no preamble, no explanation. "
            "Start directly with a project title heading. "
            "Be thorough but concise. Include: project purpose, key tools and their config, "
            "workflows, connected Nexus projects, and any AI guidance relevant to this module type."
        )

        peers_str   = ", ".join(peers) if peers else "none"
        init_prompt = (
            f"Module type: {self._module_key}\n"
            f"Project slug: {self._slug}\n"
            f"Connected Nexus projects: {peers_str}\n\n"
            f"Project config:\n{project_cfg}\n\n"
            f"Module template knowledge:\n{template}\n\n"
            f"Current CLAUDE.md:\n{current_md}\n\n"
            f"User description: {description}\n\n"
            "Write the new CLAUDE.md for this project."
        )

        chat_log.write("[/init] Generating personalized context…")
        try:
            from nexus.ai.client import AIClient
            client = AIClient()
            new_md = await client.chat(
                messages      = [{"role": "user", "content": init_prompt}],
                system_prompt = init_system,
                skill_scopes  = [],
            )
        except Exception:
            log.exception("/init AI call failed for %s", self._slug)
            chat_log.write("[error] /init failed — see log.")
            return

        claude_md_path = _PROJECTS_DIR / self._slug / "CLAUDE.md"
        try:
            claude_md_path.write_text(new_md, encoding="utf-8")
        except Exception:
            log.exception("Failed to write CLAUDE.md for %s", self._slug)
            chat_log.write("[error] Could not write CLAUDE.md — see log.")
            return

        chat_log.write("[/init] ✓ CLAUDE.md rewritten with personalized context.")
        self.app.notify("CLAUDE.md rewritten — this project's AI context is now personalized.")

    # ── Clear ─────────────────────────────────────────────────────────────────

    def _confirm_clear(self) -> None:
        from nexus.ui.tiles import ConfirmDeleteModal
        self.app.push_screen(
            ConfirmDeleteModal("chat history"),
            self._do_clear,
        )

    def _do_clear(self, confirmed: bool) -> None:
        if not confirmed:
            return
        self._messages = []
        try:
            self._history_path().unlink(missing_ok=True)
        except Exception:
            pass
        try:
            chat_log = self.query_one("#chat-log", RichLog)
        except NoMatches:
            return
        chat_log.clear()
        chat_log.write("[info] Chat history cleared.")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _read_claude_md(self) -> str:
        try:
            return (_PROJECTS_DIR / self._slug / "CLAUDE.md").read_text(errors="replace")
        except FileNotFoundError:
            return ""

    def _read_template(self) -> str:
        try:
            return (_MODULES_DIR / self._module_key / "CLAUDE.template.md").read_text(errors="replace")
        except FileNotFoundError:
            return ""

    def _read_project_config(self) -> str:
        try:
            return (_PROJECTS_DIR / self._slug / "config.yaml").read_text(errors="replace")
        except FileNotFoundError:
            return "(no config)"

    def _list_peers(self) -> list[str]:
        try:
            from nexus.core.project_manager import list_projects
            return [p.slug for p in list_projects() if p.slug != self._slug]
        except Exception:
            return []
