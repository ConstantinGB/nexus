from __future__ import annotations
import asyncio
import os
import shutil

import httpx
from textual.app import ComposeResult
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Header, Footer, Label, Input, Button, Checkbox,
    TabbedContent, TabPane, Select,
)
from textual.containers import Vertical, Horizontal, ScrollableContainer

from nexus.core.config_manager import load_global_config, save_global_config
from nexus.core.logger import get

log = get("ui.settings_screen")

_PROVIDERS = ["login", "api_key", "local"]

_CAPABILITIES = [
    "reasoning",
    "coding",
    "embedding",
    "instruct",
    "function_calling",
    "vision",
    "stt_tts",
]

_CAP_LABELS = {
    "reasoning":        "Reasoning",
    "coding":           "Coding",
    "embedding":        "Embedding",
    "instruct":         "Instruct",
    "function_calling": "Function calling",
    "vision":           "Vision",
    "stt_tts":          "STT / TTS",
}

_PROVIDER_BTN = {
    "login":   "btn-provider-login",
    "api_key": "btn-provider-api-key",
    "local":   "btn-provider-local",
}

# (module_id, binary_to_check, display_name, apt_pkg_or_None)
_MODULE_DEPS: list[tuple[str, str, str, str | None]] = [
    ("git",       "git",           "Git",           "git"),
    ("web",       "node",          "Node.js",       "nodejs"),
    ("web",       "npm",           "npm",           "npm"),
    ("journal",   "pdflatex",      "pdflatex",      "texlive-latex-base"),
    ("game",      "godot",         "Godot Engine",  None),
    ("streaming", "obs",           "OBS Studio",    "obs-studio"),
    ("emulator",  "retroarch",     "RetroArch",     "retroarch"),
    ("vault",     "gpg",           "GnuPG",         "gnupg"),
    ("vault",     "age",           "age",           "age"),
    ("vault",     "keepassxc-cli", "KeePassXC CLI", "keepassxc"),
    ("server",    "docker",        "Docker",        "docker.io"),
    ("localai",   "ollama",        "Ollama",        "ollama"),
    ("backup",    "restic",        "restic",        "restic"),
]

_INSTALL_CMDS: dict[str, str] = {
    "git":               "sudo apt install -y git",
    "nodejs":            "sudo apt install -y nodejs npm",
    "npm":               "sudo apt install -y nodejs npm",
    "texlive-latex-base":"sudo apt install -y texlive-latex-base",
    "obs-studio":        "sudo apt install -y obs-studio",
    "retroarch":         "sudo apt install -y retroarch",
    "gnupg":             "sudo apt install -y gnupg",
    "age":               "sudo apt install -y age",
    "keepassxc":         "sudo apt install -y keepassxc",
    "docker.io":         "sudo apt install -y docker.io",
    "ollama":            "curl -fsSL https://ollama.com/install.sh | sh",
    "restic":            "sudo apt install -y restic",
}


class _ResticRequiredModal(ModalScreen[bool]):
    DEFAULT_CSS = """
    _ResticRequiredModal { align: center middle; }
    _ResticRequiredModal > Vertical {
        width: 52; height: auto; padding: 2 3;
        background: #2D1B4E; border: solid #00B4FF;
    }
    _ResticRequiredModal Label { height: auto; margin-bottom: 1; color: #E0E0FF; }
    _ResticRequiredModal Button { margin-top: 1; }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(
                "restic is not installed.\n\n"
                "Backup functionality requires restic.\n"
                "Go to the Setup tab to install it."
            )
            yield Button("Go to Setup →", id="btn-modal-ok", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(True)


class SettingsScreen(Screen):
    BINDINGS = [("escape", "dismiss", "Close")]

    DEFAULT_CSS = """
    SettingsScreen { background: #1A0A2E; }
    SettingsScreen Header { background: #2D1B4E; color: #00B4FF; }
    SettingsScreen Footer { background: #2D1B4E; color: #00FF88; }

    SettingsScreen TabbedContent { height: 1fr; }
    SettingsScreen TabPane       { padding: 1 2; }

    .setting-section {
        background: #2D1B4E;
        border: solid #3A2260;
        padding: 1 2;
        margin-bottom: 1;
        height: auto;
    }
    .setting-section.active-section { border: solid #00B4FF; }

    .section-title  { color: #00B4FF; text-style: bold; height: 1; margin-bottom: 1; }
    .section-desc   { color: #8080AA; height: 3; }
    .field-label    { color: #00FF88; height: 1; margin-top: 1; }
    .hint           { color: #555588; height: 1; }
    .status-ok      { color: #00FF88; height: 1; }
    .status-err     { color: #FF4444; height: 1; }
    .status-pending { color: #8080AA; height: 1; }

    /* Provider selector bar */
    #provider-bar   { height: 3; margin-bottom: 1; }

    .provider-btn {
        width: 12;
        margin-right: 1;
        background: #2D1B4E;
        color: #8080AA;
        border: solid #3A2260;
    }
    .provider-btn.provider-selected {
        background: #1A1040;
        color: #00B4FF;
        border: solid #00B4FF;
    }
    .mode-toggle-btn {
        width: 14;
        background: #2D1B4E;
        color: #00FF88;
        border: solid #3A2260;
        margin-left: 1;
    }

    /* Provider detail sections */
    #api-key-section { height: auto; }
    #local-section   { height: auto; }
    #login-section   { height: auto; }
    #verify-bar      { height: 3; }

    /* Model section */
    #model-section   { height: auto; background: #2D1B4E; border: solid #3A2260;
                        padding: 1 2; margin-bottom: 1; }
    #model-section.active-section { border: solid #00B4FF; }
    #model-basic     { height: auto; }
    #model-advanced  { height: auto; }

    .model-row            { height: 3; margin-bottom: 0; }
    .model-cap-label      { width: 18; color: #E0E0FF; content-align: left middle; height: 3; }
    .model-row Input      { width: 1fr; }

    /* Square checkboxes: solid border so it looks like a box, not a pill */
    .model-row Checkbox {
        width: 5;
        height: 3;
        border: solid #3A2260;
        background: #1A0A2E;
        padding: 0;
        color: #555577;
    }
    .model-row Checkbox > .toggle--button {
        background: transparent;
    }
    .model-row Checkbox.-on {
        border: solid #00B4FF;
        color: #00B4FF;
    }
    .model-row Checkbox.-on > .toggle--button {
        background: transparent;
    }

    /* Dim model input when its capability is disabled */
    .model-row Input:disabled {
        color: #444455;
        background: #130822;
        border: solid #241540;
    }

    #save-bar         { height: 3; margin-top: 1; }
    #save-bar Button  { margin-right: 1; }

    .general-row    { height: 3; padding: 0 1; border-bottom: solid #241540; }
    .general-label  { color: #E0E0FF; width: 1fr; }
    .general-value  { color: #8080AA; }

    /* System Modules tab */
    .sysmod-card { height: auto; }
    .sysmod-card Checkbox {
        height: 3;
        border: solid #3A2260;
        background: #1A0A2E;
        color: #555577;
    }
    .sysmod-card Checkbox > .toggle--button { background: transparent; }
    .sysmod-card Checkbox.-on { border: solid #00B4FF; color: #00B4FF; }
    #sysmod-save-bar { height: 3; margin-top: 1; }
    #sysmod-save-bar Button { margin-right: 1; }
    #sysmod-backup-schedule-row { height: 3; margin-top: 1; }
    #sysmod-backup-schedule-row Select { width: 1fr; }
    #sysmod-backup-schedule-row Button { width: 14; margin-left: 1; height: 3; }

    /* Setup tab */
    #setup-mode-bar      { height: 3; margin-bottom: 1; }
    .setup-mode-btn {
        width: 20;
        margin-right: 1;
        background: #2D1B4E;
        color: #8080AA;
        border: solid #3A2260;
    }
    .setup-mode-btn.mode-selected {
        background: #1A1040;
        color: #00B4FF;
        border: solid #00B4FF;
    }
    .mod-group-label { color: #00FF88; text-style: bold; height: 1; margin-top: 1; }
    .dep-row         { height: 3; padding: 0 1; border-bottom: solid #241540; }
    .dep-name        { width: 1fr; color: #E0E0FF; content-align: left middle; }
    .dep-status-ok   { width: 12; color: #00FF88; content-align: left middle; }
    .dep-status-miss { width: 12; color: #FF4444; content-align: left middle; }
    .dep-install-btn { width: 12; height: 3; }
    #setup-log {
        height: 8;
        border: solid #3A2260;
        background: #130822;
        padding: 0 1;
        margin-top: 1;
        color: #8080AA;
    }
    """

    def __init__(self):
        super().__init__()
        self._cfg: dict = {}
        self._provider      = "api_key"
        self._model_mode    = "basic"
        self._install_mode  = "direct"

    # ── Compose ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        self._cfg = load_global_config()
        ai = self._cfg.get("ai", {})
        self._provider = ai.get("provider", "api_key")
        if self._provider not in _PROVIDERS:
            self._provider = "api_key"
        self._model_mode = ai.get("model_mode", "basic")
        if self._model_mode not in ("basic", "advanced"):
            self._model_mode = "basic"

        api_key        = ai.get("api_key", "")
        local_endpoint = ai.get("local_endpoint", "http://localhost:11434")
        local_model    = ai.get("local_model", "")
        basic_model    = ai.get("model", "")
        models         = ai.get("models", {})

        yield Header()
        with TabbedContent():
            # ── AI tab ────────────────────────────────────────────────────
            with TabPane("AI Provider", id="tab_ai"):
                with ScrollableContainer():

                    # Provider selector + mode toggle
                    with Horizontal(id="provider-bar"):
                        yield Button("Login",   id="btn-provider-login",
                                     classes="provider-btn")
                        yield Button("API Key", id="btn-provider-api-key",
                                     classes="provider-btn")
                        yield Button("Local",   id="btn-provider-local",
                                     classes="provider-btn")
                        toggle_label = "Advanced" if self._model_mode == "basic" else "Basic"
                        yield Button(toggle_label, id="btn-mode-toggle",
                                     classes="mode-toggle-btn")

                    # ── Login section ─────────────────────────────────────
                    with Vertical(id="login-section", classes="setting-section"):
                        yield Label("Claude.ai Login", classes="section-title")
                        yield Label(
                            "Sign in at claude.ai to use your subscription.\n"
                            "Browser-based OAuth login is not yet supported in the terminal UI.\n"
                            "Use an API key in the meantime.",
                            classes="section-desc",
                        )

                    # ── API key section ───────────────────────────────────
                    with Vertical(id="api-key-section", classes="setting-section"):
                        yield Label("Anthropic API Key", classes="section-title")
                        yield Label("API key from console.anthropic.com", classes="hint")
                        yield Input(
                            value=api_key,
                            placeholder="sk-ant-…",
                            password=True,
                            id="input-api-key",
                        )
                        with Horizontal(id="verify-bar"):
                            yield Button("Verify", id="btn-verify", variant="default")
                            yield Label("", id="verify-status", classes="status-pending")
                        yield Label(
                            "The key is stored in config/settings.yaml (git-ignored).",
                            classes="hint",
                        )

                    # ── Local section ─────────────────────────────────────
                    with Vertical(id="local-section", classes="setting-section"):
                        yield Label("Local Model", classes="section-title")
                        yield Label("Endpoint URL:", classes="field-label")
                        yield Input(
                            value=local_endpoint,
                            placeholder="http://localhost:11434",
                            id="input-local-endpoint",
                        )
                        yield Label("Server model name (used in /v1/models):",
                                    classes="field-label")
                        yield Input(
                            value=local_model,
                            placeholder="llama3.2",
                            id="input-local-model",
                        )
                        yield Label(
                            "Compatible with any OpenAI-compatible endpoint (Ollama, LM Studio, …).",
                            classes="hint",
                        )

                    # ── Model section (Basic / Advanced) ──────────────────
                    with Vertical(id="model-section", classes="setting-section"):
                        yield Label("Model", classes="section-title")

                        # Basic: single model input
                        with Vertical(id="model-basic"):
                            yield Label("Model name:", classes="field-label")
                            yield Input(
                                value=basic_model,
                                placeholder="claude-sonnet-4-6",
                                id="input-model",
                            )

                        # Advanced: per-capability rows
                        with Vertical(id="model-advanced"):
                            for cap in _CAPABILITIES:
                                cap_cfg = models.get(cap, {})
                                with Horizontal(classes="model-row"):
                                    yield Checkbox(
                                        "",
                                        id=f"cb-{cap}",
                                        value=cap_cfg.get("enabled", True),
                                    )
                                    yield Label(
                                        _CAP_LABELS[cap],
                                        classes="model-cap-label",
                                    )
                                    yield Input(
                                        value=cap_cfg.get("model", ""),
                                        placeholder="model name…",
                                        id=f"model-{cap}",
                                    )

                    with Horizontal(id="save-bar"):
                        yield Button("Save",  id="btn-save",  variant="primary")
                        yield Button("Close", id="btn-close")

            # ── System Modules tab ────────────────────────────────────────
            with TabPane("System Modules", id="tab_system"):
                sys_cfg = self._cfg.get("system_modules", {})
                localai_cfg = sys_cfg.get("localai", {})
                backup_cfg  = sys_cfg.get("backup", {})
                with ScrollableContainer():
                    yield Label(
                        "Configure services that Nexus uses internally. "
                        "These are separate from personal project instances.",
                        classes="hint",
                    )

                    # LocalAI card
                    with Vertical(id="sysmod-localai",
                                  classes="setting-section sysmod-card"):
                        yield Label("LocalAI", classes="section-title")
                        yield Label(
                            "Local inference endpoint used by Nexus for AI features.",
                            classes="hint",
                        )
                        yield Checkbox(
                            "Enable as system AI provider",
                            id="sysmod-localai-enabled",
                            value=localai_cfg.get("enabled", False),
                        )
                        yield Label("Endpoint URL:", classes="field-label")
                        yield Input(
                            value=localai_cfg.get("endpoint",
                                                   "http://localhost:11434"),
                            placeholder="http://localhost:11434",
                            id="sysmod-localai-endpoint",
                        )
                        yield Label("Model name:", classes="field-label")
                        yield Input(
                            value=localai_cfg.get("model", ""),
                            placeholder="llama3.2",
                            id="sysmod-localai-model",
                        )

                    # Backup card
                    with Vertical(id="sysmod-backup",
                                  classes="setting-section sysmod-card"):
                        yield Label("Backup", classes="section-title")
                        yield Label(
                            "Automated backup for Nexus projects and data via restic.",
                            classes="hint",
                        )
                        yield Checkbox(
                            "Enable automated backups",
                            id="sysmod-backup-enabled",
                            value=backup_cfg.get("enabled", False),
                        )
                        _last = backup_cfg.get("last_run")
                        _last_str = _last[:16].replace("T", " ") if _last else "Never"
                        yield Label(f"Last backup: {_last_str}",
                                    id="sysmod-backup-last-run", classes="hint")
                        yield Label("Backend (local / sftp / nfs):",
                                    classes="field-label")
                        yield Input(
                            value=backup_cfg.get("backend", "local"),
                            placeholder="local",
                            id="sysmod-backup-backend",
                        )
                        yield Label("Repository path:", classes="field-label")
                        yield Input(
                            value=backup_cfg.get("repo_path", ""),
                            placeholder="/path/to/backup/repo",
                            id="sysmod-backup-repo",
                        )
                        yield Label("Password (encryption key):",
                                    classes="field-label")
                        yield Input(
                            value=backup_cfg.get("password", ""),
                            placeholder="strong-passphrase",
                            password=True,
                            id="sysmod-backup-password",
                        )
                        yield Label("Paths to back up (comma-separated):",
                                    classes="field-label")
                        yield Input(
                            value=backup_cfg.get("paths", ""),
                            placeholder="~/nexus/projects, ~/documents",
                            id="sysmod-backup-paths",
                        )
                        yield Label("Schedule:", classes="field-label")
                        with Horizontal(id="sysmod-backup-schedule-row"):
                            yield Select(
                                [("Manual", "manual"),
                                 ("Daily", "daily"),
                                 ("Weekly", "weekly")],
                                value=backup_cfg.get("schedule", "manual"),
                                id="sysmod-backup-schedule",
                                allow_blank=False,
                            )
                            yield Button("Backup Now",
                                         id="btn-sysmod-backup-now")

                    with Horizontal(id="sysmod-save-bar"):
                        yield Button("Save",  id="btn-sysmod-save",
                                     variant="primary")
                        yield Label("", id="sysmod-save-status",
                                    classes="status-pending")

            # ── Setup tab ─────────────────────────────────────────────────
            with TabPane("Setup", id="tab_setup"):
                with ScrollableContainer():
                    yield Label(
                        "Install software required by each module. "
                        "Only 'Install Direct' mode is active; "
                        "Local and Download modes are coming soon.",
                        classes="hint",
                    )
                    with Horizontal(id="setup-mode-bar"):
                        yield Button("Install Direct",
                                     id="btn-setup-direct",
                                     classes="setup-mode-btn mode-selected")
                        yield Button("Download + Install",
                                     id="btn-setup-local",
                                     classes="setup-mode-btn")
                        yield Button("Download Only",
                                     id="btn-setup-download",
                                     classes="setup-mode-btn")

                    # Group deps by module
                    seen_modules: set[str] = set()
                    for mod_id, binary, display, apt_pkg in _MODULE_DEPS:
                        if mod_id not in seen_modules:
                            seen_modules.add(mod_id)
                            yield Label(mod_id.upper(), classes="mod-group-label")
                        present = shutil.which(binary) is not None
                        status_cls  = "dep-status-ok"   if present else "dep-status-miss"
                        status_text = "✓ installed"     if present else "✗ missing"
                        btn_id = f"btn-install-{(apt_pkg or 'manual').replace('.', '-')}"
                        with Horizontal(classes="dep-row"):
                            yield Label(display, classes="dep-name")
                            yield Label(status_text, classes=status_cls,
                                        id=f"dep-status-{binary.replace('-','_')}")
                            if apt_pkg is None:
                                yield Label("manual install",
                                            classes="dep-status-miss dep-install-btn")
                            else:
                                yield Button("Install", id=btn_id,
                                             classes="dep-install-btn")

                    yield Label("", id="setup-log")

            # ── General tab ───────────────────────────────────────────────
            with TabPane("General", id="tab_general"):
                with ScrollableContainer():
                    yield Label(
                        "General settings — more options coming soon.",
                        classes="hint",
                    )
                    with Horizontal(classes="general-row"):
                        yield Label("Log level", classes="general-label")
                        yield Label("DEBUG (always)", classes="general-value")
                    with Horizontal(classes="general-row"):
                        yield Label("Log location", classes="general-label")
                        yield Label("logs/nexus.log", classes="general-value")
                    with Horizontal(classes="general-row"):
                        yield Label("MCP servers", classes="general-label")
                        yield Label("Managed via MCP screen (press m)", classes="general-value")

        yield Footer()

    def on_mount(self) -> None:
        self._refresh_provider_buttons()
        # Defer visibility changes to after the first layout pass so that
        # display=False actually collapses the hidden containers.
        self.call_after_refresh(self._apply_initial_visibility)

    def _apply_initial_visibility(self) -> None:
        self._update_sections(self._provider)
        self._sync_advanced_inputs()

    # ── Checkbox → disable/enable sibling input ───────────────────────────────

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        cb_id = event.checkbox.id or ""
        if cb_id.startswith("cb-"):
            cap = cb_id[3:]
            try:
                self.query_one(f"#model-{cap}", Input).disabled = not event.value
            except Exception:
                pass
        elif cb_id == "sysmod-backup-enabled" and event.value:
            if shutil.which("restic") is None:
                self.app.push_screen(
                    _ResticRequiredModal(),
                    self._on_restic_modal_dismissed,
                )

    def _sync_advanced_inputs(self) -> None:
        ai     = self._cfg.get("ai", {})
        models = ai.get("models", {})
        for cap in _CAPABILITIES:
            cap_cfg = models.get(cap, {})
            try:
                self.query_one(f"#model-{cap}", Input).disabled = not cap_cfg.get("enabled", True)
            except Exception:
                pass

    # ── Provider button selection ─────────────────────────────────────────────

    def _refresh_provider_buttons(self) -> None:
        for provider, btn_id in _PROVIDER_BTN.items():
            try:
                btn = self.query_one(f"#{btn_id}", Button)
                if provider == self._provider:
                    btn.add_class("provider-selected")
                else:
                    btn.remove_class("provider-selected")
            except Exception:
                pass

    # ── Section visibility ────────────────────────────────────────────────────

    def _update_sections(self, provider: str) -> None:
        mapping = {
            "login":   "#login-section",
            "api_key": "#api-key-section",
            "local":   "#local-section",
        }
        for p, sel in mapping.items():
            try:
                widget = self.query_one(sel)
                widget.display = (p == provider)
                if p == provider:
                    widget.add_class("active-section")
                else:
                    widget.remove_class("active-section")
            except Exception:
                pass
        self._update_model_section()

    def _update_model_section(self) -> None:
        try:
            model_section = self.query_one("#model-section")
            if self._provider == "login":
                model_section.display = False
                return
            model_section.display = True
            model_section.add_class("active-section")

            show_basic = self._model_mode == "basic"
            self.query_one("#model-basic").display    = show_basic
            self.query_one("#model-advanced").display = not show_basic
        except Exception:
            pass

    # ── Button handler ────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        try:
            if bid == "btn-provider-login":
                self._provider = "login"
                self._refresh_provider_buttons()
                self.call_after_refresh(lambda: self._update_sections("login"))
            elif bid == "btn-provider-api-key":
                self._provider = "api_key"
                self._refresh_provider_buttons()
                self.call_after_refresh(lambda: self._update_sections("api_key"))
            elif bid == "btn-provider-local":
                self._provider = "local"
                self._refresh_provider_buttons()
                self.call_after_refresh(lambda: self._update_sections("local"))
            elif bid == "btn-mode-toggle":
                self._model_mode = "advanced" if self._model_mode == "basic" else "basic"
                new_label = "Advanced" if self._model_mode == "basic" else "Basic"
                self.query_one("#btn-mode-toggle", Button).label = new_label
                self.call_after_refresh(self._update_model_section)
            elif bid == "btn-verify":
                self.run_worker(self._verify_api_key())
            elif bid == "btn-save":
                self._save()
            elif bid == "btn-close":
                self.dismiss()
            elif bid == "btn-sysmod-save":
                self._save_system_modules()
            elif bid == "btn-sysmod-backup-now":
                if shutil.which("restic") is None:
                    self.app.push_screen(
                        _ResticRequiredModal(),
                        self._on_restic_modal_dismissed,
                    )
                else:
                    self.run_worker(self._do_system_backup())
            elif bid in ("btn-setup-direct", "btn-setup-local", "btn-setup-download"):
                mode_map = {
                    "btn-setup-direct":   "direct",
                    "btn-setup-local":    "local",
                    "btn-setup-download": "download",
                }
                self._install_mode = mode_map[bid]
                self._refresh_install_mode_buttons()
                if self._install_mode != "direct":
                    self.app.notify(
                        "Only 'Install Direct' mode is implemented.",
                        severity="warning",
                    )
            elif bid and bid.startswith("btn-install-"):
                apt_pkg = bid[len("btn-install-"):].replace("-", ".", 1)
                cmd = _INSTALL_CMDS.get(apt_pkg) or _INSTALL_CMDS.get(
                    apt_pkg.replace("-", ".")
                )
                if cmd and self._install_mode == "direct":
                    self.run_worker(self._run_install(apt_pkg, cmd))
        except Exception:
            log.exception("Error in settings button handler (button=%s)", bid)
            self.app.notify("Unexpected error — see log.", severity="error")

    # ── Verify API key ────────────────────────────────────────────────────────

    async def _verify_api_key(self) -> None:
        status = self.query_one("#verify-status", Label)
        key = self.query_one("#input-api-key", Input).value.strip()
        if not key:
            status.update("⚠ Enter a key first")
            status.set_classes("status-err")
            return

        status.update("Verifying…")
        status.set_classes("status-pending")
        log.debug("Verifying Anthropic API key")

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={
                        "x-api-key": key,
                        "anthropic-version": "2023-06-01",
                    },
                )
            if r.status_code == 200:
                models = r.json().get("data", [])
                first = models[0]["id"] if models else "claude"
                log.info("API key valid, first model: %s", first)
                status.update(f"✓ Valid  ({first})")
                status.set_classes("status-ok")
            else:
                log.warning("API key verification failed: HTTP %s", r.status_code)
                status.update(f"✗ Invalid  (HTTP {r.status_code})")
                status.set_classes("status-err")
        except Exception:
            log.exception("API key verification request failed")
            status.update("✗ Connection error")
            status.set_classes("status-err")

    # ── Save ──────────────────────────────────────────────────────────────────

    def _save(self) -> None:
        log.info("Saving settings, provider=%s, model_mode=%s",
                 self._provider, self._model_mode)
        try:
            cfg = load_global_config()
            cfg.setdefault("ai", {})

            cfg["ai"]["provider"]   = self._provider
            cfg["ai"]["model_mode"] = self._model_mode

            if self._provider == "api_key":
                cfg["ai"]["api_key"] = self.query_one(
                    "#input-api-key", Input
                ).value.strip()
            elif self._provider == "local":
                cfg["ai"]["local_endpoint"] = self.query_one(
                    "#input-local-endpoint", Input
                ).value.strip()
                cfg["ai"]["local_model"] = self.query_one(
                    "#input-local-model", Input
                ).value.strip()

            if self._model_mode == "basic":
                cfg["ai"]["model"] = self.query_one(
                    "#input-model", Input
                ).value.strip()
            else:
                cfg["ai"].setdefault("models", {})
                for cap in _CAPABILITIES:
                    enabled = self.query_one(f"#cb-{cap}", Checkbox).value
                    model   = self.query_one(f"#model-{cap}", Input).value.strip()
                    cfg["ai"]["models"][cap] = {"enabled": enabled, "model": model}

            save_global_config(cfg)
            log.info("Settings saved")
            self.app.notify("Settings saved.", severity="information")
        except Exception:
            log.exception("Failed to save settings")
            self.app.notify("Failed to save settings — see log.", severity="error")

    # ── System Modules save ───────────────────────────────────────────────────

    def _save_system_modules(self) -> None:
        log.info("Saving system module settings")
        try:
            cfg = load_global_config()
            cfg.setdefault("system_modules", {})

            cfg["system_modules"]["localai"] = {
                "enabled":  self.query_one("#sysmod-localai-enabled",
                                           Checkbox).value,
                "endpoint": self.query_one("#sysmod-localai-endpoint",
                                           Input).value.strip(),
                "model":    self.query_one("#sysmod-localai-model",
                                           Input).value.strip(),
            }
            cfg["system_modules"]["backup"] = {
                "enabled":   self.query_one("#sysmod-backup-enabled",
                                            Checkbox).value,
                "backend":   self.query_one("#sysmod-backup-backend",
                                            Input).value.strip(),
                "repo_path": self.query_one("#sysmod-backup-repo",
                                            Input).value.strip(),
                "password":  self.query_one("#sysmod-backup-password",
                                            Input).value.strip(),
                "paths":     self.query_one("#sysmod-backup-paths",
                                            Input).value.strip(),
                "schedule":  str(self.query_one("#sysmod-backup-schedule",
                                                Select).value),
            }
            save_global_config(cfg)
            log.info("System module settings saved")
            try:
                self.query_one("#sysmod-save-status", Label).update("✓ Saved")
                self.query_one("#sysmod-save-status").set_classes("status-ok")
            except Exception:
                pass
            self.app.notify("System module settings saved.", severity="information")
        except Exception:
            log.exception("Failed to save system module settings")
            self.app.notify("Failed to save — see log.", severity="error")

    def _on_restic_modal_dismissed(self, result: bool) -> None:
        if result:
            try:
                self.query_one(TabbedContent).active = "tab_setup"
            except Exception:
                log.exception("Failed to switch to Setup tab")

    async def _do_system_backup(self) -> None:
        from modules.backup.backup_ops import restic_ensure_initialized, restic_backup
        import asyncio as _aio

        repo      = self.query_one("#sysmod-backup-repo",    Input).value.strip()
        pw        = self.query_one("#sysmod-backup-password", Input).value.strip()
        paths_raw = self.query_one("#sysmod-backup-paths",   Input).value.strip()
        paths     = [p.strip() for p in paths_raw.split(",") if p.strip()]

        if not repo:
            self.app.notify("Set a repository path first.", severity="warning")
            return
        if not paths:
            self.app.notify("Enter at least one path to back up.", severity="warning")
            return

        self.app.notify("Initialising repository if needed…", severity="information")
        loop = _aio.get_event_loop()
        ok, msg = await loop.run_in_executor(
            None, restic_ensure_initialized, repo, pw
        )
        if not ok:
            self.app.notify(f"Init failed — {msg[:140]}", severity="error")
            log.error("restic_ensure_initialized failed: %s", msg)
            return

        self.app.notify("Backup running…", severity="information")
        ok, out = await loop.run_in_executor(
            None, restic_backup, repo, pw, paths
        )
        if ok:
            self.app.notify("System backup completed.", severity="information")
        else:
            self.app.notify(f"Backup failed — {out[:140]}", severity="error")
            log.error("system backup failed: %s", out)

    # ── Setup tab helpers ─────────────────────────────────────────────────────

    def _refresh_install_mode_buttons(self) -> None:
        mode_btns = {
            "direct":   "btn-setup-direct",
            "local":    "btn-setup-local",
            "download": "btn-setup-download",
        }
        for mode, btn_id in mode_btns.items():
            try:
                btn = self.query_one(f"#{btn_id}", Button)
                if mode == self._install_mode:
                    btn.add_class("mode-selected")
                else:
                    btn.remove_class("mode-selected")
            except Exception:
                pass

    async def _run_install(self, apt_pkg: str, cmd: str) -> None:
        log_label = self.query_one("#setup-log", Label)
        log_label.update(f"Running: {cmd}\n…")
        log.info("Setup install: %s", cmd)
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await proc.communicate()
            output = stdout.decode(errors="replace").strip()
            if proc.returncode == 0:
                log_label.update(f"✓ {apt_pkg} installed.\n{output[-300:]}")
                self.app.notify(f"{apt_pkg} installed.", severity="information")
            else:
                log_label.update(f"✗ Install failed (exit {proc.returncode}).\n"
                                  f"{output[-300:]}")
                self.app.notify(f"Install failed — see log area.", severity="error")
        except Exception:
            log.exception("Install subprocess failed: %s", cmd)
            log_label.update("✗ Subprocess error — see nexus.log.")
            self.app.notify("Install error — see log.", severity="error")
