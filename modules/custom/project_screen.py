from __future__ import annotations
import asyncio
import shlex
from pathlib import Path

from textual.app import ComposeResult
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Header, Footer, Label, Button, Log, RichLog, DirectoryTree
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.core.project_manager import ProjectInfo
from nexus.ui.tui.base_project_screen import InputModal
from nexus.ui.tui.chat_panel import ChatPanel

log = get("custom.project_screen")

_PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"


class ProjectScreen(Screen):
    BINDINGS = [("escape", "dismiss", "Back")]

    DEFAULT_CSS = """
    ProjectScreen { background: $theme-bg; }
    ProjectScreen Header { background: $theme-surface; color: $theme-border; }
    ProjectScreen Footer { background: $theme-surface; color: $theme-accent2; }

    #top-bar       { height: 3; background: $theme-surface; padding: 0 2;
                     border-bottom: solid $theme-border-dim; }
    #project-title { color: $theme-border; text-style: bold; width: 1fr; }
    .panel-btn        { margin-left: 1; }
    .panel-btn-active { border: solid $theme-accent2; color: $theme-accent2; }

    #pane-row      { height: 1fr; }

    #context-pane  { width: 35; border-right: solid $theme-border-dim; display: block; }
    .pane-title    { color: $theme-accent2; text-style: bold; height: 1;
                     background: $theme-surface; padding: 0 1; }
    #context-log   { height: 10; background: $theme-bg; }
    #file-tree     { height: 1fr; background: #0E0620; }

    ProjectScreen ChatPanel { display: block; width: 1fr; border-left: none; }

    #terminal-panel { width: 1fr; height: 1fr;
                      border-left: solid $theme-border-dim; display: none; }

    #cmd-bar       { height: 3; background: $theme-surface;
                     border-top: solid $theme-border-dim; padding: 0 1; }
    #cmd-bar Button { margin-right: 1; height: 3; }
    .util-btn      { background: $theme-bg; color: $theme-text-dim;
                     border: solid $theme-border-dim; }
    """

    def __init__(self, project: ProjectInfo) -> None:
        super().__init__()
        self.project      = project
        self._commands: list[dict] = []
        self._panel_mode: str = "chat"
        self._context_visible: bool = True

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load(self) -> None:
        from nexus.core.config_manager import load_project_config
        cfg = load_project_config(self.project.slug)
        self._commands = cfg.get("custom", {}).get("commands", [])

    def _read_claude_md(self) -> str:
        md_path = _PROJECTS_DIR / self.project.slug / "CLAUDE.md"
        try:
            return md_path.read_text(errors="replace")
        except FileNotFoundError:
            return (
                "(CLAUDE.md not found)\n\n"
                f"Edit the file at projects/{self.project.slug}/CLAUDE.md "
                "to give the AI context about this project."
            )

    # ── Compose ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        from nexus.ui.tui.project_tabs import ProjectTabBar
        self._load()
        yield Header()
        yield ProjectTabBar()
        with Horizontal(id="top-bar"):
            yield Label(self.project.name, id="project-title")
            yield Button("📄 Context", id="btn-toggle-context", classes="panel-btn")
            yield Button("💬 Chat",    id="btn-panel-chat",     classes="panel-btn")
            yield Button("⌨ Claude",   id="btn-panel-claude",   classes="panel-btn")
            yield Button("$ Shell",    id="btn-panel-bash",     classes="panel-btn")

        with Horizontal(id="pane-row"):
            with Vertical(id="context-pane"):
                yield Label("CONTEXT  (CLAUDE.md)", classes="pane-title")
                yield Log(id="context-log", highlight=False, auto_scroll=False)
                yield Label("FILES", classes="pane-title")
                yield DirectoryTree(
                    str(_PROJECTS_DIR / self.project.slug),
                    id="file-tree",
                )

            yield ChatPanel(
                self.project.slug,
                "custom",
                ["global", "custom"],
                id="chat-panel",
            )
            yield Vertical(id="terminal-panel")

        with Horizontal(id="cmd-bar"):
            for i, cmd in enumerate(self._commands):
                yield Button(cmd["label"], id=f"btn-cmd-{i}")
            yield Button("📁 Open Folder", id="btn-open-folder", classes="util-btn")
            yield Button("⟳ Reload",       id="btn-reload",      classes="util-btn")

        yield Footer()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self.call_after_refresh(self._init_context)
        self.call_after_refresh(self._apply_panel_default)
        self.call_after_refresh(self._activate_context_btn)

    def _activate_context_btn(self) -> None:
        try:
            self.query_one("#btn-toggle-context", Button).add_class("panel-btn-active")
        except Exception:
            pass

    def _apply_panel_default(self) -> None:
        from nexus.core.config_manager import load_global_config
        default = load_global_config().get("ai", {}).get("default_panel", "chat")
        if default == "chat":
            self._set_panel_mode("chat")
        elif default == "claude_code":
            self.run_worker(self._launch_claude())

    def _init_context(self) -> None:
        try:
            ctx = self.query_one("#context-log", Log)
        except NoMatches:
            return
        for line in self._read_claude_md().splitlines():
            ctx.write_line(line)

    # ── Button handler ────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        try:
            if bid == "btn-toggle-context":
                self._toggle_context()
            elif bid == "btn-panel-chat":
                new_mode = "none" if self._panel_mode == "chat" else "chat"
                self._set_panel_mode(new_mode)
            elif bid == "btn-panel-claude":
                if self._panel_mode == "claude_code":
                    self._set_panel_mode("none")
                else:
                    self.run_worker(self._launch_claude())
            elif bid == "btn-panel-bash":
                if self._panel_mode == "bash":
                    self._set_panel_mode("none")
                else:
                    self.run_worker(self._launch_bash())
            elif bid == "btn-open-folder":
                import subprocess
                from nexus.core.platform import open_path
                try:
                    subprocess.Popen(open_path(str(_PROJECTS_DIR / self.project.slug)))
                except Exception:
                    log.exception("Failed to open folder")
                    self.app.notify("Could not open folder.", severity="error")
            elif bid == "btn-reload":
                self._reload()
            elif bid.startswith("btn-cmd-"):
                idx = int(bid[len("btn-cmd-"):])
                if idx < len(self._commands):
                    self.run_worker(self._run_command(self._commands[idx]["cmd"]))
        except Exception:
            log.exception("Button handler error (bid=%s)", bid)
            self.app.notify("Unexpected error — see log.", severity="error")

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        from nexus.ui.tui.text_editor_screen import TextEditorScreen
        path = event.path
        try:
            content = path.read_text(errors="replace")
        except Exception:
            self.app.notify(f"Cannot read: {path.name}", severity="error")
            return
        suffix = path.suffix.lower()
        lang = {".md": "markdown", ".py": "python", ".yaml": "yaml", ".yml": "yaml",
                ".sh": "bash", ".json": "json", ".toml": "toml"}.get(suffix, "text")
        self.app.push_screen(
            TextEditorScreen(content, language=lang, title=path.name),
            lambda saved, p=path: self._save_file(p, saved),
        )

    def _save_file(self, path: Path, content: str | None) -> None:
        if content is None:
            return
        try:
            path.write_text(content)
            self.app.notify(f"Saved: {path.name}", severity="information")
        except Exception:
            log.exception("Failed to save file: %s", path)
            self.app.notify("Could not save file — see log.", severity="error")

    def action_dismiss(self, result=None) -> None:
        for tid in ("#claude-terminal", "#bash-terminal"):
            try:
                from nexus.ui.tui.terminal_widget import Terminal
                self.query_one(tid, Terminal).stop()
            except NoMatches:
                pass
        if hasattr(self.app, "close_project_tab"):
            self.app.close_project_tab(self.project.slug)
        self.dismiss(result)

    # ── Context pane ──────────────────────────────────────────────────────────

    def _toggle_context(self) -> None:
        self._context_visible = not self._context_visible
        try:
            self.query_one("#context-pane").display = self._context_visible
        except NoMatches:
            pass
        try:
            btn = self.query_one("#btn-toggle-context", Button)
            if self._context_visible:
                btn.add_class("panel-btn-active")
            else:
                btn.remove_class("panel-btn-active")
        except NoMatches:
            pass

    # ── Panel mode ────────────────────────────────────────────────────────────

    def _set_panel_mode(self, mode: str) -> None:
        self._panel_mode = mode
        try:
            self.query_one("#chat-panel", ChatPanel).display = (mode == "chat")
        except NoMatches:
            pass
        try:
            self.query_one("#terminal-panel").display = (mode in ("claude_code", "bash"))
        except NoMatches:
            pass
        for tid, tmode in [("claude-terminal", "claude_code"), ("bash-terminal", "bash")]:
            try:
                self.query_one(f"#{tid}").display = (mode == tmode)
            except NoMatches:
                pass
        for bid, active_mode in [
            ("btn-panel-chat",   "chat"),
            ("btn-panel-claude", "claude_code"),
            ("btn-panel-bash",   "bash"),
        ]:
            try:
                btn = self.query_one(f"#{bid}", Button)
                if mode == active_mode:
                    btn.add_class("panel-btn-active")
                else:
                    btn.remove_class("panel-btn-active")
            except NoMatches:
                pass

    # ── Terminal panels ───────────────────────────────────────────────────────

    async def _launch_claude(self) -> None:
        import shutil
        from nexus.ui.tui.terminal_widget import Terminal

        if not shutil.which("claude"):
            self.app.notify(
                "'claude' not found on PATH — install Claude Code first.",
                severity="error",
            )
            return

        self._set_panel_mode("claude_code")

        try:
            self.query_one("#claude-terminal")
            return
        except NoMatches:
            pass

        terminal = Terminal(
            command="claude",
            cwd=str(_PROJECTS_DIR / self.project.slug),
            id="claude-terminal",
        )
        try:
            panel = self.query_one("#terminal-panel")
        except NoMatches:
            return
        await panel.mount(terminal)
        terminal.start()
        terminal.focus()

    async def _launch_bash(self) -> None:
        import shutil
        from nexus.ui.tui.terminal_widget import Terminal

        shell = shutil.which("bash") or shutil.which("sh")
        if not shell:
            self.app.notify("No shell found on PATH.", severity="error")
            return

        self._set_panel_mode("bash")

        try:
            self.query_one("#bash-terminal")
            return
        except NoMatches:
            pass

        terminal = Terminal(
            command=shell,
            cwd=str(_PROJECTS_DIR / self.project.slug),
            id="bash-terminal",
        )
        try:
            panel = self.query_one("#terminal-panel")
        except NoMatches:
            return
        await panel.mount(terminal)
        terminal.start()
        terminal.focus()

    def on_terminal_process_stopped(self, event) -> None:
        widget = getattr(event, "control", None) or getattr(event, "widget", None)
        wid = getattr(widget, "id", None) if widget else None
        try:
            if widget is not None:
                widget.remove()
        except Exception:
            pass
        if wid == "claude-terminal" and self._panel_mode == "claude_code":
            self._set_panel_mode("none")
        elif wid == "bash-terminal" and self._panel_mode == "bash":
            self._set_panel_mode("none")
        elif wid is None:
            for tid, mode in [("claude-terminal", "claude_code"), ("bash-terminal", "bash")]:
                try:
                    self.query_one(f"#{tid}").remove()
                    if self._panel_mode == mode:
                        self._set_panel_mode("none")
                except NoMatches:
                    pass

    # ── Custom commands ───────────────────────────────────────────────────────

    async def _run_command(self, cmd: str) -> None:
        from nexus.ui.tui.chat_panel import ChatPanel
        try:
            chat_log = self.query_one(ChatPanel).query_one("#chat-log", RichLog)
        except NoMatches:
            return
        chat_log.write(f"[cmd] $ {cmd}")
        try:
            try:
                args = shlex.split(cmd)
            except ValueError as exc:
                chat_log.write(f"[cmd] ✗ invalid command syntax: {exc}")
                return
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(_PROJECTS_DIR / self.project.slug),
            )
            if proc.stdout:
                async for raw in proc.stdout:
                    try:
                        chat_log.write(raw.decode(errors="replace").rstrip())
                    except Exception:
                        break
            await proc.wait()
            try:
                chat_log.write(
                    f"[cmd] ✓ done (exit {proc.returncode})"
                    if proc.returncode == 0
                    else f"[cmd] ✗ exit {proc.returncode}"
                )
            except Exception:
                pass
        except Exception:
            log.exception("Custom command failed: %s", cmd)
            try:
                chat_log.write("[cmd] ✗ error — see log.")
            except Exception:
                pass

    # ── Reload ────────────────────────────────────────────────────────────────

    def _reload(self) -> None:
        try:
            ctx = self.query_one("#context-log", Log)
            ctx.clear()
            for line in self._read_claude_md().splitlines():
                ctx.write_line(line)
        except NoMatches:
            pass
        self.app.notify("Context reloaded.", severity="information")
