from __future__ import annotations
import asyncio
from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Label, Button, Log, TextArea
from textual.containers import Vertical, Horizontal, ScrollableContainer

from nexus.core.logger import get
from nexus.core.project_manager import ProjectInfo
from nexus.ui.base_project_screen import InputModal

log = get("custom.project_screen")

_PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"


class CustomProjectScreen(Screen):
    BINDINGS = [("escape", "dismiss", "Back")]

    DEFAULT_CSS = """
    CustomProjectScreen { background: #1A0A2E; }
    CustomProjectScreen Header { background: #2D1B4E; color: #00B4FF; }
    CustomProjectScreen Footer { background: #2D1B4E; color: #00FF88; }

    #top-bar       { height: 3; background: #2D1B4E; padding: 0 2;
                     border-bottom: solid #3A2260; }
    #project-title { color: #00B4FF; text-style: bold; width: 1fr; }

    #pane-row      { height: 1fr; }

    #context-pane  { width: 35; border-right: solid #3A2260; }
    .pane-title    { color: #00FF88; text-style: bold; height: 1;
                     background: #2D1B4E; padding: 0 1; }
    #context-log   { height: 1fr; background: #130822; }

    #chat-pane     { width: 1fr; }
    #chat-log      { height: 1fr; background: #0A0518; }
    #chat-input    { height: 5; border: solid #3A2260; margin: 0; }
    #input-row     { height: 3; padding: 0 1; }
    #input-row Button { margin-right: 1; }

    .no-ai-notice  { color: #555588; height: 1; padding: 0 1; margin-top: 1; }

    #cmd-bar       { height: 3; background: #2D1B4E;
                     border-top: solid #3A2260; padding: 0 1; }
    #cmd-bar Button { margin-right: 1; height: 3; }
    .util-btn      { background: #1A0A2E; color: #8080AA;
                     border: solid #3A2260; }
    """

    def __init__(self, project: ProjectInfo) -> None:
        super().__init__()
        self.project    = project
        self._messages: list[dict] = []
        self._ai_client = None
        self._has_ai    = False
        self._claude_md = ""
        self._commands: list[dict] = []  # [{label, cmd}, ...]

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load(self) -> None:
        from nexus.core.config_manager import load_global_config, load_project_config, is_ai_configured

        md_path = _PROJECTS_DIR / self.project.slug / "CLAUDE.md"
        try:
            self._claude_md = md_path.read_text(errors="replace")
        except FileNotFoundError:
            self._claude_md = (
                "(CLAUDE.md not found)\n\n"
                "Edit the file at projects/{slug}/CLAUDE.md "
                "to give the AI context about this project."
            )

        cfg = load_project_config(self.project.slug)
        self._commands = cfg.get("custom", {}).get("commands", [])

        ai_cfg = load_global_config().get("ai", {})
        if is_ai_configured(ai_cfg):
            from nexus.ai.client import AIClient
            self._ai_client = AIClient()
            self._has_ai = True

    # ── Compose ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        self._load()
        yield Header()
        with Horizontal(id="top-bar"):
            yield Label(self.project.name, id="project-title")

        with Horizontal(id="pane-row"):
            # Left — context (CLAUDE.md)
            with Vertical(id="context-pane"):
                yield Label("CONTEXT  (CLAUDE.md)", classes="pane-title")
                yield Log(id="context-log", highlight=False, auto_scroll=False)

            # Right — chat
            with Vertical(id="chat-pane"):
                yield Label("CHAT", classes="pane-title")
                yield Log(id="chat-log", auto_scroll=True)
                if self._has_ai:
                    yield TextArea("", id="chat-input")
                    with Horizontal(id="input-row"):
                        yield Button("Send ▶", id="btn-send", variant="primary")
                        yield Button("Clear",  id="btn-clear")
                else:
                    yield Label(
                        "No AI provider configured — press s → AI Provider to set one up.",
                        classes="no-ai-notice",
                    )

        # Bottom — custom commands + utility buttons
        with Horizontal(id="cmd-bar"):
            for i, cmd in enumerate(self._commands):
                yield Button(cmd["label"], id=f"btn-cmd-{i}")
            yield Button("+ Add Command", id="btn-add-cmd",  classes="util-btn")
            yield Button("⟳ Reload",      id="btn-reload",   classes="util-btn")

        yield Footer()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self.call_after_refresh(self._init_display)

    def _init_display(self) -> None:
        ctx = self.query_one("#context-log", Log)
        for line in self._claude_md.splitlines():
            ctx.write_line(line)

        chat = self.query_one("#chat-log", Log)
        if self._has_ai:
            chat.write_line(
                "[assistant] Hello! I've read your project context. "
                "Ask me anything about this project."
            )
        else:
            chat.write_line(
                "[info] Custom commands below will run without AI. "
                "Add an AI provider in Settings to enable chat."
            )

    # ── Button handler ────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        try:
            if bid == "btn-send":
                self.run_worker(self._send_message())
            elif bid == "btn-clear":
                self._clear_chat()
            elif bid == "btn-add-cmd":
                self.app.push_screen(
                    InputModal(
                        "Add Command",
                        "Enter label and shell command separated by a colon\n"
                        'e.g.  Build: make build',
                        placeholder="Build: make build",
                    ),
                    self._on_add_cmd_input,
                )
            elif bid == "btn-reload":
                self._reload()
            elif bid.startswith("btn-cmd-"):
                idx = int(bid[len("btn-cmd-"):])
                if idx < len(self._commands):
                    self.run_worker(self._run_command(self._commands[idx]["cmd"]))
        except Exception:
            log.exception("Button handler error (bid=%s)", bid)
            self.app.notify("Unexpected error — see log.", severity="error")

    # ── Chat ──────────────────────────────────────────────────────────────────

    async def _send_message(self) -> None:
        if not self._ai_client:
            return
        ta   = self.query_one("#chat-input", TextArea)
        text = ta.text.strip()
        if not text:
            return
        await ta.load_text("")

        chat = self.query_one("#chat-log", Log)
        chat.write_line(f"[you] {text}")
        self._messages.append({"role": "user", "content": text})

        chat.write_line("[assistant] …")
        try:
            reply = await self._ai_client.chat(
                messages      = self._messages,
                system_prompt = self._claude_md,
                skill_scopes  = ["global", "custom"],
            )
        except Exception:
            log.exception("Custom AI chat failed")
            chat.write_line("[error] AI request failed — see log.")
            self._messages.pop()
            return

        # Replace the "…" placeholder with the real reply
        chat.write_line(f"[assistant] {reply}")
        self._messages.append({"role": "assistant", "content": reply})

    def _clear_chat(self) -> None:
        self._messages.clear()
        chat = self.query_one("#chat-log", Log)
        chat.clear()
        if self._has_ai:
            chat.write_line("[assistant] Chat cleared. How can I help?")

    # ── Custom commands ───────────────────────────────────────────────────────

    async def _run_command(self, cmd: str) -> None:
        chat = self.query_one("#chat-log", Log)
        chat.write_line(f"[cmd] $ {cmd}")
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(_PROJECTS_DIR / self.project.slug),
            )
            if proc.stdout:
                async for raw in proc.stdout:
                    chat.write_line(raw.decode(errors="replace").rstrip())
            await proc.wait()
            chat.write_line(
                f"[cmd] ✓ done (exit {proc.returncode})"
                if proc.returncode == 0
                else f"[cmd] ✗ exit {proc.returncode}"
            )
        except Exception:
            log.exception("Custom command failed: %s", cmd)
            chat.write_line("[cmd] ✗ error — see log.")

    def _on_add_cmd_input(self, value: str | None) -> None:
        if not value or ":" not in value:
            if value is not None:
                self.app.notify('Format: Label: shell command', severity="warning")
            return
        label, _, cmd = value.partition(":")
        label = label.strip()
        cmd   = cmd.strip()
        if not label or not cmd:
            self.app.notify("Both label and command are required.", severity="warning")
            return
        self._commands.append({"label": label, "cmd": cmd})
        self._save_commands()
        self.run_worker(self._mount_new_cmd_button(label, len(self._commands) - 1))
        self.app.notify(f"Command '{label}' added.", severity="information")

    async def _mount_new_cmd_button(self, label: str, idx: int) -> None:
        cmd_bar = self.query_one("#cmd-bar")
        add_btn = self.query_one("#btn-add-cmd", Button)
        await cmd_bar.mount(Button(label, id=f"btn-cmd-{idx}"), before=add_btn)

    def _save_commands(self) -> None:
        from nexus.core.config_manager import load_project_config, save_project_config
        cfg = load_project_config(self.project.slug)
        cfg.setdefault("custom", {})["commands"] = self._commands
        save_project_config(self.project.slug, cfg)

    # ── Reload ────────────────────────────────────────────────────────────────

    def _reload(self) -> None:
        md_path = _PROJECTS_DIR / self.project.slug / "CLAUDE.md"
        try:
            self._claude_md = md_path.read_text(errors="replace")
        except FileNotFoundError:
            pass

        ctx = self.query_one("#context-log", Log)
        ctx.clear()
        for line in self._claude_md.splitlines():
            ctx.write_line(line)

        self._clear_chat()
        self.app.notify("Context reloaded.", severity="information")
