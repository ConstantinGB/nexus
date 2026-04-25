from __future__ import annotations
import asyncio
from pathlib import Path

from textual.app import ComposeResult
from textual.screen import ModalScreen, Screen
from textual.widgets import Header, Footer, Label, Button, Log, Input
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.core.project_manager import ProjectInfo
from nexus.core.config_manager import load_project_config, save_project_config
from nexus.ui.chat_panel import ChatPanel

log = get("ui.base_project_screen")


def _screen_css(name: str) -> str:
    """Return the 3 screen-scoped CSS rules every project screen needs."""
    return (
        f"{name} {{ background: #1A0A2E; }}\n"
        f"{name} Header {{ background: #2D1B4E; color: #00B4FF; }}\n"
        f"{name} Footer {{ background: #2D1B4E; color: #00FF88; }}\n"
    )


class InputModal(ModalScreen):
    """Simple single-input modal used across project screens."""

    DEFAULT_CSS = """
    InputModal { align: center middle; }
    #im-dialog {
        background: #2D1B4E; border: solid #00B4FF;
        padding: 1 2; width: 60; height: auto;
    }
    #im-title  { color: #00B4FF; text-style: bold; height: 2; }
    #im-prompt { color: #E0E0FF; height: 1; margin-bottom: 1; }
    #im-input  { margin-bottom: 1; }
    #im-btns   { height: 3; }
    #im-btns Button { margin-right: 1; }
    """

    def __init__(self, title: str, prompt: str, placeholder: str = "") -> None:
        super().__init__()
        self._title = title
        self._prompt = prompt
        self._placeholder = placeholder

    def compose(self) -> ComposeResult:
        with Vertical(id="im-dialog"):
            yield Label(self._title, id="im-title")
            yield Label(self._prompt, id="im-prompt")
            yield Input(placeholder=self._placeholder, id="im-input")
            with Horizontal(id="im-btns"):
                yield Button("OK", id="im-ok", variant="primary")
                yield Button("Cancel", id="im-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "im-ok":
            val = self.query_one("#im-input", Input).value.strip()
            self.dismiss(val or None)
        else:
            self.dismiss(None)

    def on_input_submitted(self, _: Input.Submitted) -> None:
        val = self.query_one("#im-input", Input).value.strip()
        self.dismiss(val or None)


class BaseProjectScreen(Screen):
    """
    Shared base for all skeleton module project screens.

    Subclasses set MODULE_KEY, MODULE_LABEL, SETUP_FIELDS and override:
      _compose_action_buttons() -> list[Button]
      async _populate_content()
      _handle_action(bid)
      _on_before_save(data) -> dict   (optional extra keys to store)
    """

    MODULE_KEY:   str        = ""
    MODULE_LABEL: str        = ""
    SETUP_FIELDS: list[dict] = []   # {"id", "label", "placeholder", "optional"?, "password"?}

    BINDINGS = [("escape", "dismiss", "Back")]

    DEFAULT_CSS = """
    #top-bar {
        height: 3;
        background: #2D1B4E;
        padding: 0 2;
        border-bottom: solid #3A2260;
    }
    #project-title { color: #00B4FF; text-style: bold; width: 1fr; }
    #project-meta  { color: #8080AA; }

    #action-bar {
        height: 3;
        padding: 0 2;
        background: #241540;
        border-bottom: solid #3A2260;
    }
    #action-bar Button { margin-right: 1; }

    #setup-pane {
        background: #2D1B4E;
        border: solid #00B4FF;
        padding: 1 2;
        width: 72;
        height: auto;
        align: center middle;
        margin: 2 4;
    }
    #setup-title { color: #00B4FF; text-style: bold; height: 2; }
    #setup-error { color: #FF4444; height: 1; }
    #setup-btns  { height: 3; margin-top: 1; }
    #setup-btns Button { margin-right: 1; }

    #body-row    { height: 1fr; }
    #main-pane   { width: 1fr; height: 1fr; }
    #content-area { height: 1fr; padding: 1 2; overflow-y: auto; }
    #btn-toggle-chat { margin-left: 1; }

    #output-log { height: 8; background: #0A0518; border: solid #3A2260; }

    .field-label   { color: #00FF88; height: 1; margin-top: 1; }
    .section-label { color: #00FF88; height: 1; margin-top: 1; }
    .hint          { color: #555588; height: 1; }
    .info-row      { height: 1; }
    .info-key      { color: #8080AA; width: 22; }
    .info-val      { color: #E0E0FF; width: 1fr; }
    .status-ok     { color: #00FF88; }
    .status-err    { color: #FF4444; }
    """

    def __init__(self, project: ProjectInfo) -> None:
        super().__init__()
        self.project = project
        self._cfg: dict = {}
        self._mod: dict = {}

    # ── Config helpers ────────────────────────────────────────────────────────

    def _load_cfg(self) -> None:
        self._cfg = load_project_config(self.project.slug)
        self._mod = self._cfg.get(self.MODULE_KEY, {})

    def _save_cfg(self, module_data: dict) -> None:
        module_data["configured"] = True
        self._cfg[self.MODULE_KEY] = module_data
        save_project_config(self.project.slug, self._cfg)
        self._mod = module_data

    def _is_configured(self) -> bool:
        return bool(self._mod.get("configured", False))

    # ── Overrideable hooks ────────────────────────────────────────────────────

    def _compose_action_buttons(self) -> list:
        """Return a list of Button widgets for the action bar."""
        return []

    async def _populate_content(self) -> None:
        """Override to fill #content-area with module-specific widgets."""

    def _handle_action(self, bid: str | None) -> None:
        """Override to handle module-specific button IDs."""

    def _on_before_save(self, data: dict) -> dict:
        """Override to compute extra config keys before saving. Return extra dict."""
        return {}

    # ── Compose ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        self._load_cfg()
        meta = self.MODULE_LABEL
        if self.project.description:
            meta = f"{self.MODULE_LABEL} · {self.project.description}"

        yield Header()
        with Horizontal(id="top-bar"):
            yield Label(self.project.name, id="project-title")
            yield Label(meta, id="project-meta")
            yield Button("💬 AI", id="btn-toggle-chat")
        with Horizontal(id="action-bar"):
            yield from self._compose_action_buttons()

        with Vertical(id="setup-pane"):
            yield Label(f"Configure — {self.project.name}", id="setup-title")
            for field in self.SETUP_FIELDS:
                yield Label(field["label"], classes="field-label")
                yield Input(
                    placeholder=field.get("placeholder", ""),
                    id=f"setup-{field['id']}",
                    password=field.get("password", False),
                )
            yield Label("", id="setup-error")
            with Horizontal(id="setup-btns"):
                yield Button("Save", id="btn-save-setup", variant="primary")

        with Horizontal(id="body-row"):
            with Vertical(id="main-pane"):
                with Vertical(id="content-area"):
                    pass
            yield ChatPanel(
                self.project.slug,
                self.MODULE_KEY,
                ["global", self.MODULE_KEY],
                id="chat-panel",
            )

        yield Log(id="output-log", auto_scroll=True)
        yield Footer()

    def on_mount(self) -> None:
        if self._is_configured():
            self.query_one("#setup-pane").display = False
            self.query_one("#action-bar").display = True
            self.run_worker(self._populate_content())
        else:
            self.query_one("#action-bar").display = False

    # ── Button dispatcher ─────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        try:
            if bid == "btn-save-setup":
                self._handle_save_setup()
            elif bid == "btn-toggle-chat":
                self._toggle_chat()
            else:
                self._handle_action(bid)
        except Exception:
            log.exception("Button handler error: %s", bid)
            self.app.notify("Unexpected error — see log.", severity="error")

    def _handle_save_setup(self) -> None:
        data: dict = {}
        for field in self.SETUP_FIELDS:
            fid = field["id"]
            val = self.query_one(f"#setup-{fid}", Input).value.strip()
            if not val and not field.get("optional", False):
                self.query_one("#setup-error", Label).update(
                    f"'{field['label']}' is required."
                )
                return
            data[fid] = val

        extra = self._on_before_save(data)
        data.update(extra)
        self._save_cfg(data)
        self._reload_screen()

    def _toggle_chat(self) -> None:
        try:
            panel = self.query_one("#chat-panel", ChatPanel)
            panel.display = not panel.display
        except Exception:
            pass

    def _reload_screen(self) -> None:
        self._load_cfg()
        self.query_one("#setup-pane").display = False
        self.query_one("#action-bar").display = True
        self.run_worker(self._populate_content())

    # ── Command runner ────────────────────────────────────────────────────────

    async def _run_cmd(self, cmd: list[str], cwd: str | None = None) -> None:
        ui_log = self.query_one("#output-log", Log)
        cmd_str = " ".join(str(c) for c in cmd)
        ui_log.write_line(f"$ {cmd_str}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *[str(c) for c in cmd],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=cwd,
            )
            assert proc.stdout
            async for raw in proc.stdout:
                ui_log.write_line(raw.decode(errors="replace").rstrip())
            await proc.wait()
            ui_log.write_line(f"✓ Exited {proc.returncode}")
        except FileNotFoundError:
            ui_log.write_line(f"✗ Not found: {cmd[0]}")
            self.app.notify(f"'{cmd[0]}' not found on PATH.", severity="error")
        except Exception:
            log.exception("Command failed: %s", cmd)
            ui_log.write_line("✗ Error — see log.")
