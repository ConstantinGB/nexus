from __future__ import annotations
import asyncio
from pathlib import Path

from textual.app import ComposeResult
from textual.css.query import NoMatches
from textual.screen import ModalScreen, Screen
from textual.widgets import Header, Footer, Label, Button, Log, Input
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.core.project_manager import (
    ProjectInfo, update_project_meta, update_project_path, move_project_files,
)
from nexus.core.config_manager import load_project_config, save_project_config
from nexus.core.platform import open_path
from nexus.ui.tui.chat_panel import ChatPanel
from nexus.ui.tui.dir_picker import DirPickerModal
from nexus.ui.tui.setup_form import SetupForm

log = get("ui.base_project_screen")


def _screen_css(name: str) -> str:
    """Return the 3 screen-scoped CSS rules every project screen needs."""
    return (
        f"{name} {{ background: $theme-bg; }}\n"
        f"{name} Header {{ background: $theme-surface; color: $theme-border; }}\n"
        f"{name} Footer {{ background: $theme-surface; color: $theme-accent2; }}\n"
    )


class InputModal(ModalScreen):
    """Simple single-input modal used across project screens."""

    DEFAULT_CSS = """
    InputModal { align: center middle; }
    #im-dialog {
        background: $theme-surface; border: solid $theme-border;
        padding: 1 2; width: 60; height: auto;
    }
    #im-title  { color: $theme-border; text-style: bold; height: 2; }
    #im-prompt { color: $theme-text; height: 1; margin-bottom: 1; }
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
        event.stop()
        if event.button.id == "im-ok":
            val = self.query_one("#im-input", Input).value.strip()
            self.dismiss(val or None)
        else:
            self.dismiss(None)

    def on_input_submitted(self, _: Input.Submitted) -> None:
        val = self.query_one("#im-input", Input).value.strip()
        self.dismiss(val or None)


class SudoModal(ModalScreen[str | None]):
    """Password prompt for sudo commands. Orange accent distinguishes it from InputModal."""

    DEFAULT_CSS = """
    SudoModal { align: center middle; }
    #sudo-dialog {
        background: $theme-surface; border: solid #FF8800;
        padding: 1 2; width: 60; height: auto;
    }
    #sudo-title  { color: #FF8800; text-style: bold; height: 2; }
    #sudo-prompt { color: $theme-text; height: 1; margin-bottom: 1; }
    #sudo-input  { margin-bottom: 1; }
    #sudo-btns   { height: 3; }
    #sudo-btns Button { margin-right: 1; }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="sudo-dialog"):
            yield Label("sudo — enter password", id="sudo-title")
            yield Label("This command requires administrator privileges.", id="sudo-prompt")
            yield Input(placeholder="password", password=True, id="sudo-input")
            with Horizontal(id="sudo-btns"):
                yield Button("OK", id="sudo-ok", variant="primary")
                yield Button("Cancel", id="sudo-cancel")

    def on_mount(self) -> None:
        self.query_one("#sudo-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        val = self.query_one("#sudo-input", Input).value
        self.dismiss(val if event.button.id == "sudo-ok" and val else None)

    def on_input_submitted(self, _: Input.Submitted) -> None:
        val = self.query_one("#sudo-input", Input).value
        self.dismiss(val if val else None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class EditProjectModal(ModalScreen):
    DEFAULT_CSS = """
    EditProjectModal { align: center middle; }
    #ep-dialog {
        background: $theme-surface; border: solid $theme-border;
        padding: 1 2; width: 70; height: auto;
    }
    #ep-title  { color: $theme-border; text-style: bold; height: 2; }
    #ep-btns   { height: 3; margin-top: 1; }
    #ep-btns Button { margin-right: 1; }
    .ep-path-row { height: 3; }
    .ep-path-row Input { width: 1fr; }
    .ep-path-row Button { width: 12; margin-left: 1; }
    """

    def __init__(self, name: str, description: str, current_path: str = "") -> None:
        super().__init__()
        self._name = name
        self._description = description
        self._current_path = current_path

    def compose(self) -> ComposeResult:
        with Vertical(id="ep-dialog"):
            yield Label("Edit Project", id="ep-title")
            yield Label("Name:", classes="field-label")
            yield Input(value=self._name, id="ep-name")
            yield Label("Description:", classes="field-label")
            yield Input(value=self._description, id="ep-desc")
            yield Label("Path (leave blank for default):", classes="field-label")
            with Horizontal(classes="ep-path-row"):
                yield Input(value=self._current_path, id="ep-path",
                            placeholder="~/my-project-folder")
                yield Button("Browse…", id="ep-browse")
            with Horizontal(id="ep-btns"):
                yield Button("Save", id="ep-save", variant="primary")
                yield Button("Cancel", id="ep-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id
        if bid == "ep-browse":
            current = self.query_one("#ep-path", Input).value or None
            self.app.push_screen(DirPickerModal(start=current), self._set_path)
        elif bid == "ep-save":
            name = self.query_one("#ep-name", Input).value.strip()
            if name:
                self.dismiss({
                    "name": name,
                    "description": self.query_one("#ep-desc", Input).value.strip(),
                    "path": self.query_one("#ep-path", Input).value.strip(),
                })
            else:
                self.app.notify("Name cannot be empty.", severity="error")
        else:
            self.dismiss(None)

    def _set_path(self, path: str | None) -> None:
        if path:
            self.query_one("#ep-path", Input).value = path

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "ep-name":
            self.query_one("#ep-desc", Input).focus()
        elif event.input.id == "ep-desc":
            self.query_one("#ep-path", Input).focus()
        elif event.input.id == "ep-path":
            name = self.query_one("#ep-name", Input).value.strip()
            if name:
                self.dismiss({
                    "name": name,
                    "description": self.query_one("#ep-desc", Input).value.strip(),
                    "path": self.query_one("#ep-path", Input).value.strip(),
                })
            else:
                self.app.notify("Name cannot be empty.", severity="error")


class ConfirmModal(ModalScreen[bool]):
    """Generic yes/no confirmation modal for destructive actions."""

    DEFAULT_CSS = """
    ConfirmModal { align: center middle; }
    #cm-box {
        background: $theme-surface; border: solid #FF4444;
        padding: 1 2; width: 56; height: auto;
    }
    #cm-title   { color: #FF4444; text-style: bold; height: 2; }
    #cm-detail  { color: $theme-text; height: auto; margin-bottom: 1; }
    #cm-hint    { color: $theme-text-dim; height: 1; margin-bottom: 1; }
    #cm-btns    { height: 3; margin-top: 1; }
    #cm-btns Button { margin-right: 1; }
    """

    def __init__(
        self,
        title: str,
        detail: str,
        hint: str = "This action cannot be undone.",
        confirm_label: str = "Delete",
    ) -> None:
        super().__init__()
        self._title         = title
        self._detail        = detail
        self._hint          = hint
        self._confirm_label = confirm_label

    def compose(self) -> ComposeResult:
        with Vertical(id="cm-box"):
            yield Label(self._title,         id="cm-title")
            yield Label(self._detail,        id="cm-detail")
            yield Label(self._hint,          id="cm-hint")
            with Horizontal(id="cm-btns"):
                yield Button(self._confirm_label, id="cm-yes",    variant="error")
                yield Button("Cancel",            id="cm-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(event.button.id == "cm-yes")


class MissingDepsModal(ModalScreen):
    """Shown on module open when one or more required binaries are absent."""

    DEFAULT_CSS = """
    MissingDepsModal { align: center middle; }
    #mdm-dialog {
        background: $theme-surface; border: solid #FF8800;
        padding: 1 2; width: 60; height: auto;
    }
    #mdm-title  { color: #FF8800; text-style: bold; height: 2; }
    #mdm-body   { color: $theme-text; height: auto; margin-bottom: 1; }
    #mdm-btns   { height: 3; }
    #mdm-btns Button { margin-right: 1; }
    """

    def __init__(self, missing: list[str]) -> None:
        super().__init__()
        self._missing = missing

    def compose(self) -> ComposeResult:
        body = "\n".join(f"  - {name}" for name in self._missing)
        with Vertical(id="mdm-dialog"):
            yield Label("Missing Software", id="mdm-title")
            yield Label(
                f"The following tools are not installed:\n{body}",
                id="mdm-body",
            )
            with Horizontal(id="mdm-btns"):
                yield Button("Open Settings", id="mdm-settings", variant="primary")
                yield Button("Dismiss",       id="mdm-dismiss")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss("settings" if event.button.id == "mdm-settings" else None)


class InputModeModal(ModalScreen[str | None]):
    """Picker for which input panel mode to open."""

    DEFAULT_CSS = """
    InputModeModal { align: center middle; }
    #imm-box {
        background: $theme-surface; border: solid $theme-border;
        padding: 1 2; width: 32; height: auto;
    }
    #imm-title { color: $theme-border; text-style: bold; height: 2; }
    .imm-opt { width: 1fr; height: 3; margin-bottom: 1; text-align: left; }
    #imm-cancel { margin-top: 1; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="imm-box"):
            yield Label("Open input panel", id="imm-title")
            yield Button("AI Chat",      id="imm-chat",   classes="imm-opt")
            yield Button("Claude",       id="imm-claude", classes="imm-opt")
            yield Button("Shell",        id="imm-shell",  classes="imm-opt")
            yield Button("Close panel",  id="imm-none",   classes="imm-opt")
            yield Button("Cancel",       id="imm-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        mapping = {
            "imm-chat":   "chat",
            "imm-claude": "claude_code",
            "imm-shell":  "bash",
            "imm-none":   "none",
        }
        bid = event.button.id or ""
        if bid == "imm-cancel":
            self.dismiss(None)
        elif bid in mapping:
            self.dismiss(mapping[bid])


class BaseProjectScreen(Screen):
    """
    Shared base for all skeleton module project screens.

    Subclasses set MODULE_KEY, MODULE_LABEL, SETUP_FIELDS and override:
      _compose_action_buttons() -> list[Button]
      async _populate_content()
      _handle_action(bid)
      _on_before_save(data) -> dict   (optional extra keys to store)
    """

    MODULE_KEY:       str                    = ""
    MODULE_LABEL:     str                    = ""
    SETUP_FIELDS:     list[dict]             = []   # {"id", "label", "placeholder", "optional"?, "password"?}
    REQUIRED_BINARIES: list[tuple[str, str]] = []   # (binary, display_name)

    BINDINGS = [
        ("escape",   "dismiss",     "Back"),
        ("pageup",   "scroll_up",   "Scroll Up"),
        ("pagedown", "scroll_down", "Scroll Down"),
    ]

    DEFAULT_CSS = """
    #top-bar {
        height: 3;
        background: $theme-surface;
        padding: 0 2;
        border-bottom: solid $theme-border-dim;
    }
    #project-title { color: $theme-border; text-style: bold; width: 1fr; }
    #project-meta  { color: $theme-text-dim; }

    #action-bar {
        height: 3;
        padding: 0 2;
        background: $theme-surface;
        border-bottom: solid $theme-border-dim;
    }
    #action-bar Button { margin-right: 1; }

    #setup-pane {
        background: $theme-surface;
        border: solid $theme-border;
        padding: 1 2;
        width: 72;
        height: auto;
        align: center middle;
        margin: 2 4;
    }

    #body-row    { height: 1fr; }
    #main-pane   { width: 1fr; height: 1fr; min-width: 0; }
    #content-area { height: 1fr; padding: 1 2; overflow-y: auto; }
    .panel-btn          { margin-left: 1; }
    .panel-btn-active   { border: solid $theme-accent2; color: $theme-accent2; }
    #btn-open-folder   { margin-left: 1; }
    #btn-edit-project  { margin-left: 1; }
    #chat-panel {
        width: 1fr;
        height: 1fr;
        border-left: solid $theme-border-dim;
        background: $theme-bg;
        display: none;
    }
    #terminal-panel {
        width: 1fr;
        height: 1fr;
        border-left: solid $theme-border-dim;
        display: none;
    }

    #output-log { height: 8; background: $theme-bg; border: solid $theme-border-dim; }

    .setup-field-row { height: 3; }
    .setup-field-row Input  { width: 1fr; }
    .browse-btn { width: 10; margin-left: 1; }
    .field-label   { color: $theme-accent2; height: 1; margin-top: 1; }
    .section-label { color: $theme-accent2; height: 1; margin-top: 1; }
    .hint          { color: $theme-text-dim; height: 1; }
    .info-row      { height: 1; }
    .info-key      { color: $theme-text-dim; width: 22; }
    .info-val      { color: $theme-text; width: 1fr; }
    .status-ok     { color: #00FF88; }
    .status-err    { color: #FF4444; }
    """

    def __init__(self, project: ProjectInfo) -> None:
        super().__init__()
        self.project = project
        self._cfg: dict = {}
        self._mod: dict = {}
        self._panel_mode: str = "none"

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

    async def _safe_populate(self) -> None:
        """Wrapper that silently drops NoMatches if the screen is dismissed mid-worker."""
        try:
            await self._populate_content()
        except NoMatches:
            pass

    def _handle_action(self, bid: str | None) -> None:
        """Override to handle module-specific button IDs."""

    def _on_before_save(self, data: dict) -> dict:
        """Override to compute extra config keys before saving. Return extra dict."""
        return {}

    def _primary_folder(self) -> Path | None:
        """Override to return the primary working directory for this project."""
        return None

    def _open_primary_folder(self) -> None:
        p = self._primary_folder()
        if p and p.exists():
            self.run_worker(self._run_cmd(open_path(p)))
        else:
            self.app.notify("No folder configured or folder does not exist.", severity="warning")

    # ── Compose ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        from nexus.ui.tui.project_tabs import ProjectTabBar
        self._load_cfg()
        meta = self.MODULE_LABEL
        if self.project.description:
            meta = f"{self.MODULE_LABEL} · {self.project.description}"

        yield Header()
        yield ProjectTabBar()
        with Horizontal(id="top-bar"):
            yield Label(self.project.name, id="project-title")
            yield Label(meta, id="project-meta")
            yield Button("📁", id="btn-open-folder", tooltip="Open project folder")
            yield Button("⚙", id="btn-edit-project", tooltip="Edit name & description")
            yield Button("⌨", id="btn-panel-input", classes="panel-btn", tooltip="Open input panel")
        with Horizontal(id="action-bar"):
            yield from self._compose_action_buttons()

        with Vertical(id="setup-pane"):
            yield SetupForm(self.SETUP_FIELDS, self.project, self.MODULE_KEY, id="setup-form")

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
            yield Vertical(id="terminal-panel")

        yield Log(id="output-log", auto_scroll=True)
        yield Footer()

    def on_mount(self) -> None:
        if self._is_configured():
            self.query_one("#setup-pane").display = False
            self.query_one("#action-bar").display = True
            self._apply_panel_default()
            self.run_worker(self._safe_populate())
            self.call_after_refresh(self._check_required_binaries)
        else:
            self.query_one("#action-bar").display = False
            self.query_one("#body-row").display = False

    def _check_required_binaries(self) -> None:
        import shutil
        missing = [name for bin_, name in self.REQUIRED_BINARIES if not shutil.which(bin_)]
        if not missing:
            return

        def _on_modal_dismiss(result: str | None) -> None:
            if result == "settings":
                from nexus.ui.tui.settings_screen import SettingsScreen
                self.app.push_screen(SettingsScreen(initial_tab="tab_setup"))

        self.app.push_screen(MissingDepsModal(missing), _on_modal_dismiss)

    # ── Message handler for SetupForm ─────────────────────────────────────────

    def on_setup_form_saved(self, event: SetupForm.Saved) -> None:
        try:
            extra = self._on_before_save(event.data)
        except Exception as _e:
            try:
                self.query_one("#sf-error", Label).update(str(_e))
            except Exception:
                pass
            return
        event.data.update(extra)
        self._save_cfg(event.data)
        self._reload_screen()

    # ── Button dispatcher ─────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        try:
            if bid == "btn-panel-input":
                def _apply_mode(mode: str | None) -> None:
                    if mode is None:
                        return
                    if mode == "none":
                        self._set_panel_mode("none")
                    elif mode == "chat":
                        new = "none" if self._panel_mode == "chat" else "chat"
                        self._set_panel_mode(new)
                    elif mode == "claude_code":
                        if self._panel_mode == "claude_code":
                            self._set_panel_mode("none")
                        else:
                            self.run_worker(self._launch_claude())
                    elif mode == "bash":
                        if self._panel_mode == "bash":
                            self._set_panel_mode("none")
                        else:
                            self.run_worker(self._launch_bash())
                self.app.push_screen(InputModeModal(), _apply_mode)
            elif bid == "btn-open-folder":
                self._open_primary_folder()
            elif bid == "btn-edit-project":
                current_path = str(self.project.path) if self.project.path else ""
                self.app.push_screen(
                    EditProjectModal(self.project.name, self.project.description,
                                     current_path),
                    self._apply_project_edit,
                )
            else:
                self._handle_action(bid)
        except Exception:
            log.exception("Button handler error: %s", bid)
            self.app.notify("Unexpected error — see log.", severity="error")

    def _apply_project_edit(self, result: dict | None) -> None:
        if not result:
            return
        new_name = result["name"]
        new_desc = result["description"]
        new_path_str = result.get("path", "").strip()

        update_project_meta(self.project.slug, new_name, new_desc)
        self.project.name = new_name
        self.project.description = new_desc
        try:
            self.query_one("#project-title", Label).update(new_name)
            meta = f"{self.MODULE_LABEL} · {new_desc}" if new_desc else self.MODULE_LABEL
            self.query_one("#project-meta", Label).update(meta)
        except Exception:
            pass

        if new_path_str:
            new_path = Path(new_path_str).expanduser()
            try:
                if new_path.resolve() != self.project.path.resolve():
                    def _on_move_confirm(do_move: bool) -> None:
                        try:
                            if do_move:
                                move_project_files(self.project.slug, new_path)
                                self.app.notify(f"Files moved to {new_path}", severity="information")
                            else:
                                update_project_path(self.project.slug, new_path)
                                self.app.notify("Path updated (files not moved).", severity="information")
                            self.project.path = new_path
                        except Exception:
                            log.exception("Failed to apply path change for %s", self.project.slug)
                            self.app.notify("Path change failed — see log.", severity="error")
                    self.app.push_screen(
                        ConfirmModal(
                            "Move Project Files?",
                            f"Move all project files to:\n{new_path}",
                            hint="Choose 'Move' to relocate files, or cancel to update path only.",
                            confirm_label="Move",
                        ),
                        _on_move_confirm,
                    )
                    return
            except Exception:
                pass

        self.app.notify("Project updated.", severity="information")

    def _apply_panel_default(self) -> None:
        if not self._is_configured():
            return
        from nexus.core.config_manager import load_global_config
        default = load_global_config().get("ai", {}).get("default_panel", "chat")
        if default == "chat":
            self._set_panel_mode("chat")
        elif default == "claude_code":
            self.call_after_refresh(lambda: self.run_worker(self._launch_claude()))
        elif default == "bash":
            self.call_after_refresh(lambda: self.run_worker(self._launch_bash()))
        else:
            self._set_panel_mode("none")

    def _set_panel_mode(self, mode: str) -> None:
        self._panel_mode = mode
        if mode in ("chat", "claude_code", "bash"):
            try:
                self.query_one("#body-row").display = True
            except NoMatches:
                pass
            if not self._is_configured():
                try:
                    self.query_one("#setup-pane").display = False
                except NoMatches:
                    pass
                try:
                    self.query_one("#main-pane").display = False
                except NoMatches:
                    pass
        else:  # "none"
            if not self._is_configured():
                try:
                    self.query_one("#body-row").display = False
                except NoMatches:
                    pass
                try:
                    self.query_one("#setup-pane").display = True
                except NoMatches:
                    pass
        # hide output-log while a panel is open so body-row gets full height
        try:
            self.query_one("#output-log").display = (mode == "none")
        except NoMatches:
            pass
        try:
            self.query_one("#chat-panel", ChatPanel).display = (mode == "chat")
        except NoMatches:
            pass
        try:
            self.query_one("#terminal-panel").display = (mode in ("claude_code", "bash"))
        except NoMatches:
            pass
        for wid, active_mode in [("#claude-terminal", "claude_code"), ("#bash-terminal", "bash")]:
            try:
                self.query_one(wid).display = (mode == active_mode)
            except NoMatches:
                pass
        # Update the single input button active state
        try:
            btn = self.query_one("#btn-panel-input", Button)
            if mode != "none":
                btn.add_class("panel-btn-active")
            else:
                btn.remove_class("panel-btn-active")
        except NoMatches:
            pass

    async def _launch_claude(self) -> None:
        import shutil
        from nexus.ui.tui.terminal_widget import Terminal

        if not shutil.which("claude"):
            self.app.notify(
                "'claude' not found on PATH — install Claude Code first.",
                severity="error",
            )
            return

        # Kill any running bash terminal before taking the shared panel
        try:
            self.query_one("#bash-terminal", Terminal).stop()
        except NoMatches:
            pass
        try:
            self.query_one("#bash-terminal").remove()
        except NoMatches:
            pass

        self._set_panel_mode("claude_code")

        # Session already alive — just make the panel visible
        try:
            self.query_one("#claude-terminal")
            return
        except NoMatches:
            pass

        terminal = Terminal(
            command="claude",
            cwd=str(self.project.path),
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
        import os, shutil
        from nexus.ui.tui.terminal_widget import Terminal

        shell = os.environ.get("SHELL", "") or shutil.which("bash") or "bash"

        # Kill any running claude terminal before taking the shared panel
        try:
            self.query_one("#claude-terminal", Terminal).stop()
        except NoMatches:
            pass
        try:
            self.query_one("#claude-terminal").remove()
        except NoMatches:
            pass

        self._set_panel_mode("bash")

        # Session already alive — just show it
        try:
            self.query_one("#bash-terminal").focus()
            return
        except NoMatches:
            pass

        terminal = Terminal(command=shell, cwd=str(self.project.path), id="bash-terminal")
        try:
            panel = self.query_one("#terminal-panel")
        except NoMatches:
            return
        await panel.mount(terminal)
        terminal.start()
        terminal.focus()

    def on_terminal_process_stopped(self, _event) -> None:
        for wid in ("#claude-terminal", "#bash-terminal"):
            try:
                self.query_one(wid).remove()
            except NoMatches:
                pass
        if self._panel_mode in ("claude_code", "bash"):
            self._set_panel_mode("none")

    def action_scroll_up(self) -> None:
        try:
            self.query_one("#content-area").scroll_up(20)
        except Exception:
            pass

    def action_scroll_down(self) -> None:
        try:
            self.query_one("#content-area").scroll_down(20)
        except Exception:
            pass

    def action_dismiss(self, result=None) -> None:
        from nexus.ui.tui.terminal_widget import Terminal
        for wid in ("#claude-terminal", "#bash-terminal"):
            try:
                self.query_one(wid, Terminal).stop()
            except NoMatches:
                pass
        if not getattr(self.app, "_going_home_for_new_tab", False):
            if hasattr(self.app, "close_project_tab"):
                self.app.close_project_tab(self.project.slug)
        self.app._going_home_for_new_tab = False
        self.dismiss(result)

    def _reload_screen(self) -> None:
        self._load_cfg()
        self.query_one("#setup-pane").display = False
        self.query_one("#action-bar").display = True
        self.query_one("#body-row").display = True
        try:
            self.query_one("#main-pane").display = True
        except NoMatches:
            pass
        self._apply_panel_default()
        self.run_worker(self._safe_populate())

    # ── Command runner ────────────────────────────────────────────────────────

    async def _run_cmd(self, cmd: list[str], cwd: str | None = None) -> None:
        try:
            ui_log = self.query_one("#output-log", Log)
        except Exception:
            return  # screen dismissed before worker started
        cmd_str = " ".join(str(c) for c in cmd)
        ui_log.write_line(f"$ {cmd_str}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *[str(c) for c in cmd],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=cwd,
            )
            if proc.stdout is None:
                log.error("subprocess stdout is None for %s", cmd)
                return
            async for raw in proc.stdout:
                try:
                    ui_log.write_line(raw.decode(errors="replace").rstrip())
                except Exception:
                    break  # screen dismissed mid-stream
            await proc.wait()
            try:
                ui_log.write_line(f"Exited {proc.returncode}")
            except Exception:
                pass
        except FileNotFoundError:
            try:
                ui_log.write_line(f"Not found: {cmd[0]}")
                self.app.notify(f"'{cmd[0]}' not found on PATH.", severity="error")
            except Exception:
                pass
        except Exception:
            log.exception("Command failed: %s", cmd)
            try:
                ui_log.write_line("Error — see log.")
            except Exception:
                pass
