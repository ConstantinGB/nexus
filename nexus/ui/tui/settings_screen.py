from __future__ import annotations
import asyncio
import os
import shutil
from dataclasses import dataclass

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
import nexus.core.sudo as _sudo
from nexus.ui.tui.base_project_screen import SudoModal

log = get("ui.settings_screen")

_PROVIDERS = ["anthropic", "openwebui", "openai_compat", "local"]

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
    "anthropic":    "btn-provider-anthropic",
    "openwebui":    "btn-provider-openwebui",
    "openai_compat":"btn-provider-openai-compat",
    "local":        "btn-provider-local",
}

def _detect_pm() -> str:
    for pm in ("apt-get", "dnf", "yum", "pacman"):
        if shutil.which(pm):
            return pm.replace("apt-get", "apt")
    return "unknown"

_PM = _detect_pm()


@dataclass(frozen=True)
class _DepSpec:
    module:  str
    binary:  str
    label:   str
    apt:     str | None = None
    dnf:     str | None = None
    pacman:  str | None = None
    special: str | None = None   # overrides all PMs (e.g. ollama curl script)
    pip_pkg: str | None = None   # if set, check via importlib instead of shutil.which

    def install_cmd(self) -> str | None:
        if self.special:
            return self.special
        pkg = {"apt": self.apt, "dnf": self.dnf, "yum": self.dnf,
               "pacman": self.pacman}.get(_PM)
        if not pkg:
            return None
        if _PM == "apt":
            prefix = "DEBIAN_FRONTEND=noninteractive " if self.binary == "macchanger" else ""
            return f"{prefix}sudo apt-get install -y {pkg}"
        if _PM in ("dnf", "yum"):
            return f"sudo {_PM} install -y {pkg}"
        if _PM == "pacman":
            return f"sudo pacman -S --noconfirm {pkg}"
        return None


_MODULE_DEPS: list[_DepSpec] = [
    # ── System-wide ───────────────────────────────────────────────────────────
    _DepSpec("system",   "xclip",           "xclip (X11 clipboard)",    apt="xclip",              dnf="xclip",              pacman="xclip"),
    _DepSpec("system",   "wl-paste",        "wl-clipboard (Wayland)",   apt="wl-clipboard",       dnf="wl-clipboard",       pacman="wl-clipboard"),
    # ── Module deps ───────────────────────────────────────────────────────────
    _DepSpec("git",      "git",             "Git",                      apt="git",                dnf="git",                pacman="git"),
    _DepSpec("web",      "node",            "Node.js",                  apt="nodejs",             dnf="nodejs",             pacman="nodejs"),
    _DepSpec("web",      "npm",             "npm",                      apt="npm",                dnf="npm",                pacman="npm"),
    _DepSpec("research", "rg",              "ripgrep (search)",         apt="ripgrep",            dnf="ripgrep",            pacman="ripgrep"),
    _DepSpec("research", "pandoc",          "pandoc (PDF export)",      apt="pandoc",             dnf="pandoc",             pacman="pandoc"),
    _DepSpec("research", "xelatex",         "xelatex (pandoc PDF engine)", apt="texlive-xetex",  dnf="texlive-xetex",      pacman="texlive-xetex"),
    _DepSpec("codex",    "rg",              "ripgrep (search)",         apt="ripgrep",            dnf="ripgrep",            pacman="ripgrep"),
    _DepSpec("journal",  "pdflatex",        "pdflatex",                 apt="texlive-latex-base", dnf="texlive-latex",      pacman="texlive-core"),
    _DepSpec("game",     "godot",           "Godot Engine",             apt=None,                 dnf=None,                 pacman=None),
    _DepSpec("streaming","obs",             "OBS Studio",               apt="obs-studio",         dnf="obs-studio",         pacman="obs-studio"),
    _DepSpec("emulator", "retroarch",       "RetroArch",                apt="retroarch",          dnf="retroarch",          pacman="retroarch"),
    _DepSpec("vault",    "gpg",             "GnuPG",                    apt="gnupg",              dnf="gnupg2",             pacman="gnupg"),
    _DepSpec("vault",    "age",             "age (encryption)",         apt="age",                dnf="age",                pacman="age"),
    _DepSpec("vault",    "keepassxc-cli",   "KeePassXC CLI",            apt="keepassxc",          dnf="keepassxc",          pacman="keepassxc"),
    _DepSpec("vault",    "veracrypt",       "VeraCrypt",                apt=None,                 dnf=None,                 pacman=None),
    _DepSpec("vault",    "cryptsetup",      "cryptsetup (LUKS)",        apt="cryptsetup",         dnf="cryptsetup",         pacman="cryptsetup"),
    _DepSpec("server",   "docker",          "Docker",                   apt="docker.io",          dnf="docker",             pacman="docker"),
    _DepSpec("localai",  "ollama",          "Ollama",                   special="curl -fsSL https://ollama.com/install.sh | sh"),
    _DepSpec("backup",   "restic",          "restic",                   apt="restic",             dnf="restic",             pacman="restic"),
    _DepSpec("security", "ufw",             "ufw (firewall)",           apt="ufw",                dnf="ufw",                pacman="ufw"),
    _DepSpec("security", "wg",              "WireGuard",                apt="wireguard-tools",    dnf="wireguard-tools",    pacman="wireguard-tools"),
    _DepSpec("security", "openvpn",         "OpenVPN",                  apt="openvpn",            dnf="openvpn",            pacman="openvpn"),
    _DepSpec("security", "mullvad",         "Mullvad VPN",              apt=None,                 dnf=None,                 pacman=None),
    _DepSpec("security", "protonvpn-cli",   "ProtonVPN CLI",            apt=None,                 dnf=None,                 pacman=None),
    _DepSpec("security", "fail2ban-client", "fail2ban",                 apt="fail2ban",           dnf="fail2ban",           pacman="fail2ban"),
    _DepSpec("security", "lynis",           "lynis (auditing)",         apt="lynis",              dnf="lynis",              pacman="lynis"),
    _DepSpec("security", "nmap",            "nmap",                     apt="nmap",               dnf="nmap",               pacman="nmap"),
    _DepSpec("security", "dnscrypt-proxy",  "dnscrypt-proxy",           apt="dnscrypt-proxy",     dnf="dnscrypt-proxy",     pacman="dnscrypt-proxy"),
    _DepSpec("security", "macchanger",      "macchanger",               apt="macchanger",         dnf="macchanger",         pacman="macchanger"),
    _DepSpec("security", "torsocks",        "torsocks",                 apt="torsocks",           dnf="torsocks",           pacman="torsocks"),
    _DepSpec("youtube",  "ffmpeg",          "ffmpeg (video conversion)", apt="ffmpeg",             dnf="ffmpeg",             pacman="ffmpeg"),
    _DepSpec("youtube",  "yt-dlp",          "yt-dlp (downloader)",      special="uv pip install yt-dlp",          pip_pkg="yt_dlp"),
    _DepSpec("youtube",  "faster-whisper",  "faster-whisper (transcription)", special="uv pip install faster-whisper", pip_pkg="faster_whisper"),
]


class _ResticRequiredModal(ModalScreen[bool]):
    DEFAULT_CSS = """
    _ResticRequiredModal { align: center middle; }
    _ResticRequiredModal > Vertical {
        width: 52; height: auto; padding: 2 3;
        background: $theme-surface; border: solid $theme-border;
    }
    _ResticRequiredModal Label { height: auto; margin-bottom: 1; color: $theme-text; }
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


class _OllamaSetupModal(ModalScreen[bool]):
    DEFAULT_CSS = """
    _OllamaSetupModal { align: center middle; }
    _OllamaSetupModal > Vertical {
        width: 70; height: auto; padding: 2 3;
        background: $theme-surface; border: solid $theme-border;
    }
    _OllamaSetupModal Label { height: auto; margin-bottom: 1; }
    #ollama-log { height: 4; color: $theme-text-dim; }
    #ollama-btns { height: 3; margin-top: 1; }
    #ollama-btns Button { margin-right: 1; }
    """

    def compose(self) -> ComposeResult:
        import platform as _platform
        arch = _platform.machine()
        with Vertical():
            yield Label("Ollama Setup", classes="section-title")
            yield Label(f"Detected architecture: {arch}", classes="hint")
            yield Label("Install command:", classes="field-label")
            yield Label("curl -fsSL https://ollama.com/install.sh | sh", classes="hint")
            yield Label("", id="ollama-log")
            with Horizontal(id="ollama-btns"):
                yield Button("Run Install", id="btn-ollama-install", variant="primary")
                yield Button("Cancel",      id="btn-ollama-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id
        if bid == "btn-ollama-cancel":
            self.dismiss(False)
        elif bid == "btn-ollama-install":
            event.button.disabled = True
            self.run_worker(self._do_install())

    async def _do_install(self) -> None:
        try:
            log_lbl = self.query_one("#ollama-log", Label)
        except Exception:
            return
        log_lbl.update("Installing Ollama…")
        cmd = "curl -fsSL https://ollama.com/install.sh | sh"
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await proc.communicate()
            output = stdout.decode(errors="replace").strip()
            if proc.returncode == 0:
                try:
                    self.query_one("#ollama-log", Label).update("✓ Ollama installed.")
                except Exception:
                    pass
                self.app.notify(
                    "Ollama installed. Set the endpoint in AI Config → Local.",
                    severity="information",
                )
                self.dismiss(True)
            else:
                try:
                    self.query_one("#ollama-log", Label).update(
                        f"✗ Failed (exit {proc.returncode})\n{output[-160:]}"
                    )
                except Exception:
                    pass
        except Exception as exc:
            try:
                self.query_one("#ollama-log", Label).update(f"✗ Error: {exc}")
            except Exception:
                pass


class SettingsScreen(Screen):
    BINDINGS = [("escape", "dismiss", "Close")]

    DEFAULT_CSS = """
    SettingsScreen { background: $theme-bg; }
    SettingsScreen Header { background: $theme-surface; color: $theme-border; }
    SettingsScreen Footer { background: $theme-surface; color: $theme-accent2; }

    SettingsScreen TabbedContent { height: 1fr; }
    SettingsScreen TabPane       { padding: 1 2; }

    .setting-section {
        background: $theme-surface;
        border: solid $theme-border-dim;
        padding: 1 2;
        margin-bottom: 1;
        height: auto;
    }
    .setting-section.active-section { border: solid $theme-border; }

    .section-title  { color: $theme-border; text-style: bold; height: 1; margin-bottom: 1; }
    .section-desc   { color: $theme-text-dim; height: 3; }
    .field-label    { color: $theme-accent2; height: 1; margin-top: 1; }
    .hint           { color: $theme-text-dim; height: 1; }
    .status-ok      { color: #00FF88; height: 1; }
    .status-err     { color: #FF4444; height: 1; }
    .status-pending { color: $theme-text-dim; height: 1; }

    /* Provider selector bar */
    #provider-bar   { height: 3; margin-bottom: 1; }

    .provider-btn {
        width: 14;
        margin-right: 1;
        background: $theme-surface;
        color: $theme-text-dim;
        border: solid $theme-border-dim;
    }
    .provider-btn.provider-selected {
        background: $theme-bg;
        color: $theme-border;
        border: solid $theme-border;
    }
    .mode-toggle-btn {
        width: 14;
        background: $theme-surface;
        border: solid $theme-border-dim;
        margin-left: 1;
    }
    .mode-toggle-red {
        color: #FF4444;
        border: solid #FF4444;
    }
    .mode-toggle-blue {
        color: #00B4FF;
        border: solid #00B4FF;
    }
    #mode-toggle-spacer { width: 1fr; }

    /* Provider detail sections */
    #api-key-section       { height: auto; }
    #openwebui-section     { height: auto; }
    #openai-compat-section { height: auto; }
    #local-section         { height: auto; }
    #verify-bar            { height: 3; }
    #local-test-bar        { height: 3; }
    #openwebui-test-bar    { height: 3; }
    #openai-compat-test-bar { height: 3; }
    #ollama-btn-bar        { height: 3; margin-top: 1; }

    /* Model section */
    #model-section   { height: auto; background: $theme-surface; border: solid $theme-border-dim;
                        padding: 1 2; margin-bottom: 1; }
    #model-section.active-section { border: solid $theme-border; }
    #model-basic     { height: auto; }
    #model-advanced  { height: auto; }

    .model-row            { height: 3; margin-bottom: 0; }
    .model-cap-label      { width: 18; color: $theme-text; content-align: left middle; height: 3; }
    .model-row Input      { width: 1fr; }

    .model-row Checkbox {
        width: 5;
        height: 3;
        border: solid $theme-border-dim;
        background: $theme-bg;
        padding: 0;
        color: $theme-text-dim;
    }
    .model-row Checkbox > .toggle--button { background: transparent; }
    .model-row Checkbox.-on { border: solid $theme-border; color: $theme-border; }
    .model-row Checkbox.-on > .toggle--button { background: transparent; }

    .model-row Input:disabled {
        color: $theme-border-dim;
        background: $theme-bg;
        border: solid $theme-border-dim;
    }

    #save-bar         { height: 3; margin-top: 1; }
    #save-bar Button  { margin-right: 1; }

    .general-row         { height: 3; padding: 0 1; border-bottom: solid $theme-border-dim; }
    .general-label       { color: $theme-text; width: 1fr; }
    .general-value       { color: $theme-text-dim; }
    .general-row Select  { width: 30; }
    #general-save-bar    { height: 3; margin-top: 1; }
    #appearance-save-bar { height: 3; margin-top: 1; }

    /* Shared system-module tab styles */
    .sysmod-card Checkbox {
        height: 3;
        border: solid $theme-border-dim;
        background: $theme-bg;
        color: $theme-text-dim;
    }
    .sysmod-card Checkbox > .toggle--button { background: transparent; }
    .sysmod-card Checkbox.-on { border: solid $theme-border; color: $theme-border; }

    .tab-save-bar { height: 3; margin-top: 1; }
    .tab-save-bar Button { margin-right: 1; }
    .tab-save-status { height: 1; }

    #backup-schedule-row { height: 3; margin-top: 1; }
    #backup-schedule-row Select { width: 1fr; }
    #backup-schedule-row Button { width: 14; margin-left: 1; height: 3; }

    /* Setup tab */
    #setup-mode-bar      { height: 3; margin-bottom: 1; }
    .setup-mode-btn {
        width: 20;
        margin-right: 1;
        background: $theme-surface;
        color: $theme-text-dim;
        border: solid $theme-border-dim;
    }
    .setup-mode-btn.mode-selected {
        background: $theme-bg;
        color: $theme-border;
        border: solid $theme-border;
    }
    .mod-group-label { color: $theme-accent2; text-style: bold; height: 1; margin-top: 1; }
    .dep-row         { height: 3; padding: 0 1; border-bottom: solid $theme-border-dim; }
    .dep-name        { width: 1fr; color: $theme-text; content-align: left middle; }
    .dep-status-ok   { width: 12; color: #00FF88; content-align: left middle; }
    .dep-status-miss { width: 12; color: #FF4444; content-align: left middle; }
    .dep-install-btn { width: 12; height: 3; }
    #setup-log {
        height: 8;
        border: solid $theme-border-dim;
        background: $theme-bg;
        padding: 0 1;
        margin-top: 1;
        color: $theme-text-dim;
    }
    """

    def __init__(self, initial_tab: str | None = None):
        super().__init__()
        self._cfg: dict = {}
        self._provider      = "anthropic"
        self._model_mode    = "basic"
        self._install_mode  = "direct"
        self._initial_tab   = initial_tab

    # ── Compose ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:  # noqa: C901
        self._cfg = load_global_config()
        ai = self._cfg.get("ai", {})

        self._provider = ai.get("provider", "anthropic")
        if self._provider == "api_key":
            self._provider = "anthropic"
        if self._provider not in _PROVIDERS:
            self._provider = "anthropic"

        self._model_mode = ai.get("model_mode", "basic")
        if self._model_mode not in ("basic", "advanced"):
            self._model_mode = "basic"

        providers_cfg       = ai.get("providers", {})
        api_key             = providers_cfg.get("anthropic", {}).get("api_key") or ai.get("api_key", "")
        local_endpoint      = providers_cfg.get("local", {}).get("endpoint") or ai.get("local_endpoint", "http://localhost:11434")
        local_model         = providers_cfg.get("local", {}).get("model") or ai.get("local_model", "")
        openwebui_url       = providers_cfg.get("openwebui", {}).get("base_url", "http://localhost:3000")
        openwebui_key       = providers_cfg.get("openwebui", {}).get("api_key", "")
        openwebui_model     = providers_cfg.get("openwebui", {}).get("model", "")
        openai_url          = providers_cfg.get("openai_compat", {}).get("base_url", "")
        openai_key          = providers_cfg.get("openai_compat", {}).get("api_key", "")
        openai_model        = providers_cfg.get("openai_compat", {}).get("model", "")
        basic_model         = ai.get("model", "")
        models              = ai.get("models", {})

        sys_cfg     = self._cfg.get("system_modules", {})
        backup_cfg  = sys_cfg.get("backup",   {})
        git_cfg     = sys_cfg.get("git",      {})
        cal_cfg     = sys_cfg.get("calendar", {})
        sdforge_cfg = sys_cfg.get("sdforge",  {})
        server_cfg  = sys_cfg.get("server",   {})

        yield Header()
        with TabbedContent():

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
                        yield Label("See the MCP tab or press m at home screen", classes="general-value")
                    with Horizontal(classes="general-row"):
                        yield Label("Default Input Panel", classes="general-label")
                        _panel_opts = [
                            ("Local AI",        "local"),
                            ("Claude Code CLI", "claude_code"),
                            ("Shell",           "shell"),
                        ]
                        _panel_val = ai.get("default_panel", "none")
                        _valid = {v for _, v in _panel_opts}
                        if _panel_val not in _valid:
                            _panel_val = "local"
                        yield Select(
                            _panel_opts,
                            value=_panel_val,
                            id="select-default-panel",
                            allow_blank=False,
                        )
                    with Horizontal(id="general-save-bar"):
                        yield Button("Save", id="btn-general-save", variant="primary")

            # ── Appearance tab ────────────────────────────────────────────
            with TabPane("Appearance", id="tab_appearance"):
                with ScrollableContainer():
                    from nexus.ui.tui.theme import THEMES
                    current_theme = self._cfg.get("ui", {}).get("theme", "nexus-legacy")
                    yield Label("Theme", classes="section-title")
                    yield Label(
                        "Choose a colour theme. Changes apply immediately.",
                        classes="hint",
                    )
                    yield Select(
                        [(t.label, t.name) for t in THEMES.values()],
                        value=current_theme,
                        id="select-theme",
                        allow_blank=False,
                    )
                    with Horizontal(id="appearance-save-bar"):
                        yield Button("Save", id="btn-appearance-save", variant="primary")

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

                    seen_modules: set[str] = set()
                    for dep in _MODULE_DEPS:
                        if dep.module not in seen_modules:
                            seen_modules.add(dep.module)
                            yield Label(dep.module.upper(), classes="mod-group-label")
                        if dep.pip_pkg:
                            import importlib.util
                            present = importlib.util.find_spec(dep.pip_pkg) is not None
                        else:
                            present = shutil.which(dep.binary) is not None
                        status_cls  = "dep-status-ok"  if present else "dep-status-miss"
                        status_text = "✓ installed"    if present else "✗ missing"
                        btn_id = f"btn-install-{dep.binary.replace('-', '_')}"
                        with Horizontal(classes="dep-row"):
                            yield Label(dep.label, classes="dep-name")
                            yield Label(status_text, classes=status_cls,
                                        id=f"dep-status-{dep.binary.replace('-', '_')}")
                            if dep.install_cmd() is None:
                                yield Label("manual install",
                                            classes="dep-status-miss dep-install-btn")
                            else:
                                yield Button("Install", id=btn_id,
                                             classes="dep-install-btn")

                    yield Label("", id="setup-log")

            # ── Git tab ───────────────────────────────────────────────────
            with TabPane("Git", id="tab_git"):
                with ScrollableContainer():
                    yield Label("Global Git identity used by Integrated-mode projects.", classes="hint")
                    yield Label("User name:", classes="field-label")
                    yield Input(
                        value=git_cfg.get("user_name", ""),
                        placeholder="Your Name",
                        id="git-user-name",
                    )
                    yield Label("User email:", classes="field-label")
                    yield Input(
                        value=git_cfg.get("user_email", ""),
                        placeholder="you@example.com",
                        id="git-user-email",
                    )
                    yield Label("Default remote type:", classes="field-label")
                    yield Select(
                        [("HTTPS", "https"), ("SSH", "ssh")],
                        value=git_cfg.get("default_remote", "https"),
                        id="git-remote-type",
                        allow_blank=False,
                    )
                    yield Label("Personal access token (for HTTPS):", classes="field-label")
                    yield Input(
                        value=git_cfg.get("token", ""),
                        placeholder="ghp_…",
                        password=True,
                        id="git-token",
                    )
                    yield Label("SSH key path (for SSH):", classes="field-label")
                    yield Input(
                        value=git_cfg.get("ssh_key_path", ""),
                        placeholder="~/.ssh/id_ed25519",
                        id="git-ssh-key",
                    )
                    with Horizontal(classes="tab-save-bar"):
                        yield Button("Save", id="btn-git-save", variant="primary")
                        yield Label("", id="git-save-status", classes="tab-save-status status-pending")

            # ── Backup tab ────────────────────────────────────────────────
            with TabPane("Backup", id="tab_backup"):
                with ScrollableContainer():
                    yield Label(
                        "Automated backup for Nexus projects and data via restic.",
                        classes="hint",
                    )
                    yield Checkbox(
                        "Enable automated backups",
                        id="backup-enabled",
                        value=backup_cfg.get("enabled", False),
                    )
                    _last = backup_cfg.get("last_run")
                    _last_str = _last[:16].replace("T", " ") if _last else "Never"
                    yield Label(f"Last backup: {_last_str}", id="backup-last-run", classes="hint")
                    yield Label("Backend (local / sftp / nfs):", classes="field-label")
                    yield Input(
                        value=backup_cfg.get("backend", "local"),
                        placeholder="local",
                        id="backup-backend",
                    )
                    yield Label("Repository path:", classes="field-label")
                    yield Input(
                        value=backup_cfg.get("repo_path", ""),
                        placeholder="/path/to/backup/repo",
                        id="backup-repo",
                    )
                    yield Label("Password (encryption key):", classes="field-label")
                    yield Input(
                        value=backup_cfg.get("password", ""),
                        placeholder="strong-passphrase",
                        password=True,
                        id="backup-password",
                    )
                    yield Label("Paths to back up (comma-separated):", classes="field-label")
                    yield Input(
                        value=backup_cfg.get("paths", ""),
                        placeholder="~/nexus/projects, ~/documents",
                        id="backup-paths",
                    )
                    yield Label("Schedule:", classes="field-label")
                    with Horizontal(id="backup-schedule-row"):
                        yield Select(
                            [("Manual", "manual"), ("Daily", "daily"), ("Weekly", "weekly")],
                            value=backup_cfg.get("schedule", "manual"),
                            id="backup-schedule",
                            allow_blank=False,
                        )
                        yield Button("Backup Now", id="btn-backup-now")
                    with Horizontal(classes="tab-save-bar"):
                        yield Button("Save", id="btn-backup-save", variant="primary")
                        yield Label("", id="backup-save-status", classes="tab-save-status status-pending")

            # ── Calendar tab ──────────────────────────────────────────────
            with TabPane("Calendar", id="tab_calendar"):
                with ScrollableContainer():
                    yield Label(
                        "Global calendar shared by all Integrated-mode calendar modules.",
                        classes="hint",
                    )
                    yield Label("Data directory (blank = <nexus>/config/calendar/):", classes="field-label")
                    yield Input(
                        value=cal_cfg.get("data_path", ""),
                        placeholder="~/my-calendars",
                        id="cal-data-path",
                    )
                    yield Checkbox(
                        "Enable CalDAV sync",
                        id="cal-caldav-enabled",
                        value=cal_cfg.get("caldav_enabled", False),
                    )
                    yield Label("CalDAV server URL:", classes="field-label")
                    yield Input(
                        value=cal_cfg.get("caldav_url", "http://localhost:5232/"),
                        placeholder="http://localhost:5232/",
                        id="cal-caldav-url",
                    )
                    yield Label("Username:", classes="field-label")
                    yield Input(
                        value=cal_cfg.get("caldav_user", ""),
                        placeholder="username",
                        id="cal-caldav-user",
                    )
                    yield Label("Password:", classes="field-label")
                    yield Input(
                        value=cal_cfg.get("caldav_password", ""),
                        placeholder="password",
                        password=True,
                        id="cal-caldav-password",
                    )
                    with Horizontal(classes="tab-save-bar"):
                        yield Button("Save", id="btn-calendar-save", variant="primary")
                        yield Button("Sync Now", id="btn-calendar-sync")
                        yield Label("", id="cal-save-status", classes="tab-save-status status-pending")

            # ── AI Config tab ──────────────────────────────────────────────
            with TabPane("AI Config", id="tab_ai"):
                with ScrollableContainer():

                    # Provider selector + mode toggle
                    with Horizontal(id="provider-bar"):
                        yield Button("Anthropic",    id="btn-provider-anthropic",    classes="provider-btn")
                        yield Button("OpenWebUI",    id="btn-provider-openwebui",    classes="provider-btn")
                        yield Button("OpenAI-compat",id="btn-provider-openai-compat",classes="provider-btn")
                        yield Button("Local",        id="btn-provider-local",        classes="provider-btn")
                        yield Label("", id="mode-toggle-spacer")
                        toggle_label = "Advanced" if self._model_mode == "basic" else "Basic"
                        toggle_cls   = "mode-toggle-btn mode-toggle-red" if self._model_mode == "basic" else "mode-toggle-btn mode-toggle-blue"
                        yield Button(toggle_label, id="btn-mode-toggle", classes=toggle_cls)

                    # ── Anthropic section ─────────────────────────────────
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

                    # ── OpenWebUI section ─────────────────────────────────
                    with Vertical(id="openwebui-section", classes="setting-section"):
                        yield Label("OpenWebUI", classes="section-title")
                        yield Label("Connect to a local OpenWebUI instance.", classes="hint")
                        yield Label("OpenWebUI base URL:", classes="field-label")
                        yield Input(
                            value=openwebui_url,
                            placeholder="http://localhost:3000",
                            id="input-openwebui-url",
                        )
                        yield Label("API key (issued by OpenWebUI):", classes="field-label")
                        yield Input(
                            value=openwebui_key,
                            placeholder="sk-…",
                            password=True,
                            id="input-openwebui-key",
                        )
                        yield Label("Model name (blank = OpenWebUI default):", classes="field-label")
                        yield Input(
                            value=openwebui_model,
                            placeholder="llama3.2",
                            id="input-openwebui-model",
                        )
                        with Horizontal(id="openwebui-test-bar"):
                            yield Button("Test", id="btn-openwebui-test")
                            yield Label("", id="openwebui-test-status", classes="status-pending")

                    # ── OpenAI-compat section ─────────────────────────────
                    with Vertical(id="openai-compat-section", classes="setting-section"):
                        yield Label("OpenAI-compatible Endpoint", classes="section-title")
                        yield Label("Any OpenAI-compatible API (LiteLLM, vLLM, etc.).", classes="hint")
                        yield Label("Base URL:", classes="field-label")
                        yield Input(
                            value=openai_url,
                            placeholder="http://localhost:8000",
                            id="input-openai-compat-url",
                        )
                        yield Label("API key:", classes="field-label")
                        yield Input(
                            value=openai_key,
                            placeholder="sk-…",
                            password=True,
                            id="input-openai-compat-key",
                        )
                        yield Label("Model name:", classes="field-label")
                        yield Input(
                            value=openai_model,
                            placeholder="gpt-4o",
                            id="input-openai-compat-model",
                        )
                        with Horizontal(id="openai-compat-test-bar"):
                            yield Button("Test", id="btn-openai-compat-test")
                            yield Label("", id="openai-compat-test-status", classes="status-pending")

                    # ── Local / Ollama section ────────────────────────────
                    with Vertical(id="local-section", classes="setting-section"):
                        yield Label("Local Model (Ollama / LM Studio / llama.cpp)", classes="section-title")
                        yield Label("Endpoint URL:", classes="field-label")
                        yield Input(
                            value=local_endpoint,
                            placeholder="http://localhost:11434",
                            id="input-local-endpoint",
                        )
                        yield Label("Server model name (used in /v1/models):", classes="field-label")
                        yield Input(
                            value=local_model,
                            placeholder="llama3.2",
                            id="input-local-model",
                        )
                        with Horizontal(id="local-test-bar"):
                            yield Button("Test Connection", id="btn-local-test")
                            yield Label("", id="local-test-status", classes="status-pending")
                        with Horizontal(id="ollama-btn-bar"):
                            yield Button("Ollama Setup →", id="btn-ollama-setup")
                            yield Label(
                                "Install Ollama if not already present.",
                                classes="hint",
                            )
                        yield Label(
                            "Compatible with any OpenAI-compatible endpoint.",
                            classes="hint",
                        )

                    # ── Model section (Basic / Advanced) ──────────────────
                    with Vertical(id="model-section", classes="setting-section"):
                        yield Label("Model", classes="section-title")

                        with Vertical(id="model-basic"):
                            yield Label("Model name:", classes="field-label")
                            yield Input(
                                value=basic_model,
                                placeholder="claude-sonnet-4-6",
                                id="input-model",
                            )

                        with Vertical(id="model-advanced"):
                            for cap in _CAPABILITIES:
                                cap_cfg = models.get(cap, {})
                                with Horizontal(classes="model-row"):
                                    yield Checkbox(
                                        "",
                                        id=f"cb-{cap}",
                                        value=cap_cfg.get("enabled", True),
                                    )
                                    yield Label(_CAP_LABELS[cap], classes="model-cap-label")
                                    yield Input(
                                        value=cap_cfg.get("model", ""),
                                        placeholder="model name…",
                                        id=f"model-{cap}",
                                    )

                    with Horizontal(id="save-bar"):
                        yield Button("Save",  id="btn-save",  variant="primary")
                        yield Button("Close", id="btn-close")

            # ── MCP tab ───────────────────────────────────────────────────
            with TabPane("MCP", id="tab_mcp"):
                with ScrollableContainer():
                    yield Label("MCP Servers", classes="section-title")
                    yield Label(
                        "MCP server management is available in two places:\n\n"
                        "  • GUI: nexus --gui → Settings → MCP Servers tab\n"
                        "  • TUI: press  m  at the home screen",
                        classes="hint",
                    )

            # ── SDForge tab ───────────────────────────────────────────────
            with TabPane("SDForge", id="tab_sdforge"):
                with ScrollableContainer():
                    yield Label("Global SDForge instance for Integrated-mode projects.", classes="hint")
                    yield Label("Endpoint URL:", classes="field-label")
                    yield Input(
                        value=sdforge_cfg.get("endpoint", "http://127.0.0.1:7860"),
                        placeholder="http://127.0.0.1:7860",
                        id="sdforge-endpoint",
                    )
                    yield Label("API key (if required):", classes="field-label")
                    yield Input(
                        value=sdforge_cfg.get("api_key", ""),
                        placeholder="optional",
                        password=True,
                        id="sdforge-api-key",
                    )
                    with Horizontal(classes="tab-save-bar"):
                        yield Button("Save", id="btn-sdforge-save", variant="primary")
                        yield Label("", id="sdforge-save-status", classes="tab-save-status status-pending")

            # ── Security tab ──────────────────────────────────────────────
            with TabPane("Security", id="tab_security"):
                with ScrollableContainer():
                    yield Label("Security", classes="section-title")
                    yield Label(
                        "Security tools are configured per-project.\n\n"
                        "Add the Security system module to a project from the project hub\n"
                        "to manage firewall, VPN, and auditing settings for that project.",
                        classes="hint",
                    )

            # ── Server tab ────────────────────────────────────────────────
            with TabPane("Server", id="tab_server"):
                with ScrollableContainer():
                    yield Label("Global web server for Integrated-mode projects.", classes="hint")
                    yield Label("Web root path:", classes="field-label")
                    yield Input(
                        value=server_cfg.get("web_root", ""),
                        placeholder="/var/www/html",
                        id="server-web-root",
                    )
                    yield Label("HTTP port:", classes="field-label")
                    yield Input(
                        value=str(server_cfg.get("http_port", 80)),
                        placeholder="80",
                        id="server-http-port",
                    )
                    yield Label("HTTPS port:", classes="field-label")
                    yield Input(
                        value=str(server_cfg.get("https_port", 443)),
                        placeholder="443",
                        id="server-https-port",
                    )
                    with Horizontal(classes="tab-save-bar"):
                        yield Button("Save", id="btn-server-save", variant="primary")
                        yield Label("", id="server-save-status", classes="tab-save-status status-pending")

        yield Footer()

    def on_mount(self) -> None:
        self._refresh_provider_buttons()
        self.call_after_refresh(self._apply_initial_visibility)
        if self._initial_tab:
            self.call_after_refresh(self._switch_to_initial_tab)

    def _switch_to_initial_tab(self) -> None:
        try:
            self.query_one(TabbedContent).active = self._initial_tab
        except Exception:
            pass

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
        elif cb_id == "backup-enabled" and event.value:
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
            "anthropic":    "#api-key-section",
            "openwebui":    "#openwebui-section",
            "openai_compat":"#openai-compat-section",
            "local":        "#local-section",
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
            model_section.display = True
            model_section.add_class("active-section")

            show_basic = self._model_mode == "basic"
            self.query_one("#model-basic").display    = show_basic
            self.query_one("#model-advanced").display = not show_basic
        except Exception:
            pass
        self._refresh_mode_toggle()

    def _refresh_mode_toggle(self) -> None:
        try:
            btn = self.query_one("#btn-mode-toggle", Button)
            if self._model_mode == "basic":
                btn.label = "Advanced"
                btn.remove_class("mode-toggle-blue")
                btn.add_class("mode-toggle-red")
            else:
                btn.label = "Basic"
                btn.remove_class("mode-toggle-red")
                btn.add_class("mode-toggle-blue")
        except Exception:
            pass

    # ── Button handler ────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:  # noqa: C901
        event.stop()
        bid = event.button.id
        try:
            if bid == "btn-provider-anthropic":
                self._provider = "anthropic"
                self._refresh_provider_buttons()
                self.call_after_refresh(lambda: self._update_sections("anthropic"))
            elif bid == "btn-provider-openwebui":
                self._provider = "openwebui"
                self._refresh_provider_buttons()
                self.call_after_refresh(lambda: self._update_sections("openwebui"))
            elif bid == "btn-provider-openai-compat":
                self._provider = "openai_compat"
                self._refresh_provider_buttons()
                self.call_after_refresh(lambda: self._update_sections("openai_compat"))
            elif bid == "btn-provider-local":
                self._provider = "local"
                self._refresh_provider_buttons()
                self.call_after_refresh(lambda: self._update_sections("local"))
            elif bid == "btn-mode-toggle":
                self._model_mode = "advanced" if self._model_mode == "basic" else "basic"
                self.call_after_refresh(self._update_model_section)
            elif bid == "btn-verify":
                self.run_worker(self._verify_api_key())
            elif bid == "btn-local-test":
                self.run_worker(self._test_local_connection())
            elif bid == "btn-openwebui-test":
                self.run_worker(self._test_openwebui_connection())
            elif bid == "btn-openai-compat-test":
                self.run_worker(self._test_openai_compat_connection())
            elif bid == "btn-ollama-setup":
                if shutil.which("ollama"):
                    self.app.notify("Ollama is already installed.", severity="information")
                else:
                    self.app.push_screen(_OllamaSetupModal())
            elif bid == "btn-save":
                self._save()
            elif bid == "btn-close":
                self.dismiss()
            elif bid == "btn-appearance-save":
                self._save_appearance()
            elif bid == "btn-general-save":
                self._save_general()
            elif bid == "btn-git-save":
                self._save_git()
            elif bid == "btn-backup-save":
                self._save_backup()
            elif bid == "btn-backup-now":
                if shutil.which("restic") is None:
                    self.app.push_screen(
                        _ResticRequiredModal(),
                        self._on_restic_modal_dismissed,
                    )
                else:
                    self.run_worker(self._do_system_backup())
            elif bid == "btn-calendar-save":
                self._save_calendar()
            elif bid == "btn-calendar-sync":
                self.app.notify("CalDAV sync not yet implemented.", severity="warning")
            elif bid == "btn-sdforge-save":
                self._save_sdforge()
            elif bid == "btn-server-save":
                self._save_server()
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
                suffix = bid[len("btn-install-"):]
                dep = next(
                    (d for d in _MODULE_DEPS if d.binary.replace("-", "_") == suffix), None
                )
                if dep is None:
                    self.app.notify("No install command found.", severity="warning")
                elif self._install_mode == "direct":
                    cmd = dep.install_cmd()
                    if cmd:
                        self._maybe_run_install(dep.binary, cmd)
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

    # ── Test local / OpenWebUI / OpenAI-compat connections ───────────────────

    async def _test_local_connection(self) -> None:
        endpoint = self.query_one("#input-local-endpoint", Input).value.strip().rstrip("/")
        lbl = self.query_one("#local-test-status", Label)
        lbl.update("testing…")
        lbl.set_classes("status-pending")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(f"{endpoint}/v1/models")
            if r.status_code == 200:
                models = r.json().get("data", [])
                first  = models[0]["id"] if models else "no models"
                lbl.update(f"✓ Connected  ({first})")
                lbl.set_classes("status-ok")
            else:
                lbl.update(f"✗ HTTP {r.status_code}")
                lbl.set_classes("status-err")
        except Exception as exc:
            lbl.update(f"✗ {exc}")
            lbl.set_classes("status-err")

    async def _test_openwebui_connection(self) -> None:
        base = self.query_one("#input-openwebui-url", Input).value.strip().rstrip("/")
        key  = self.query_one("#input-openwebui-key", Input).value.strip()
        lbl  = self.query_one("#openwebui-test-status", Label)
        lbl.update("testing…")
        lbl.set_classes("status-pending")
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(f"{base}/api/v1/models", headers=headers)
            if r.status_code == 200:
                data = r.json().get("data", [])
                first = data[0]["id"] if data else "no models"
                lbl.update(f"✓ Connected  ({first})")
                lbl.set_classes("status-ok")
            else:
                lbl.update(f"✗ HTTP {r.status_code}")
                lbl.set_classes("status-err")
        except Exception as exc:
            lbl.update(f"✗ {exc}")
            lbl.set_classes("status-err")

    async def _test_openai_compat_connection(self) -> None:
        base = self.query_one("#input-openai-compat-url", Input).value.strip().rstrip("/")
        key  = self.query_one("#input-openai-compat-key", Input).value.strip()
        lbl  = self.query_one("#openai-compat-test-status", Label)
        lbl.update("testing…")
        lbl.set_classes("status-pending")
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(f"{base}/v1/models", headers=headers)
            if r.status_code == 200:
                data = r.json().get("data", [])
                first = data[0]["id"] if data else "no models"
                lbl.update(f"✓ Connected  ({first})")
                lbl.set_classes("status-ok")
            else:
                lbl.update(f"✗ HTTP {r.status_code}")
                lbl.set_classes("status-err")
        except Exception as exc:
            lbl.update(f"✗ {exc}")
            lbl.set_classes("status-err")

    # ── Save — AI Config ──────────────────────────────────────────────────────

    def _save(self) -> None:
        log.info("Saving AI config, provider=%s, model_mode=%s", self._provider, self._model_mode)
        try:
            cfg = load_global_config()
            ai  = cfg.setdefault("ai", {})

            ai["provider"]   = self._provider
            ai["model_mode"] = self._model_mode
            providers = ai.setdefault("providers", {})

            if self._provider == "anthropic":
                providers.setdefault("anthropic", {})["api_key"] = (
                    self.query_one("#input-api-key", Input).value.strip()
                )
            elif self._provider == "openwebui":
                providers["openwebui"] = {
                    "base_url": self.query_one("#input-openwebui-url",   Input).value.strip(),
                    "api_key":  self.query_one("#input-openwebui-key",   Input).value.strip(),
                    "model":    self.query_one("#input-openwebui-model", Input).value.strip(),
                }
            elif self._provider == "openai_compat":
                providers["openai_compat"] = {
                    "base_url": self.query_one("#input-openai-compat-url",   Input).value.strip(),
                    "api_key":  self.query_one("#input-openai-compat-key",   Input).value.strip(),
                    "model":    self.query_one("#input-openai-compat-model", Input).value.strip(),
                }
            elif self._provider == "local":
                providers["local"] = {
                    "endpoint": self.query_one("#input-local-endpoint", Input).value.strip(),
                    "model":    self.query_one("#input-local-model",    Input).value.strip(),
                }

            if self._model_mode == "basic":
                ai["model"] = self.query_one("#input-model", Input).value.strip()
            else:
                ai.setdefault("models", {})
                for cap in _CAPABILITIES:
                    enabled = self.query_one(f"#cb-{cap}", Checkbox).value
                    model   = self.query_one(f"#model-{cap}", Input).value.strip()
                    ai["models"][cap] = {"enabled": enabled, "model": model}

            save_global_config(cfg)
            log.info("AI config saved")
            self.app.notify("Settings saved.", severity="information")
        except Exception:
            log.exception("Failed to save AI config")
            self.app.notify("Failed to save settings — see log.", severity="error")

    # ── Save — Appearance ─────────────────────────────────────────────────────

    def _save_appearance(self) -> None:
        try:
            theme_name = str(self.query_one("#select-theme", Select).value)
            cfg = load_global_config()
            cfg.setdefault("ui", {})["theme"] = theme_name
            save_global_config(cfg)
            self.app.update_theme(theme_name)
            self.app.notify("Theme applied.", severity="information")
        except Exception:
            log.exception("Failed to save appearance settings")
            self.app.notify("Failed to save — see log.", severity="error")

    # ── Save — General ────────────────────────────────────────────────────────

    def _save_general(self) -> None:
        try:
            cfg = load_global_config()
            cfg.setdefault("ai", {})["default_panel"] = str(
                self.query_one("#select-default-panel", Select).value
            )
            save_global_config(cfg)
            self.app.notify("General settings saved.", severity="information")
        except Exception:
            log.exception("Failed to save general settings")
            self.app.notify("Failed to save — see log.", severity="error")

    # ── Save — Git ────────────────────────────────────────────────────────────

    def _save_git(self) -> None:
        try:
            cfg = load_global_config()
            cfg.setdefault("system_modules", {})["git"] = {
                "user_name":      self.query_one("#git-user-name",  Input).value.strip(),
                "user_email":     self.query_one("#git-user-email", Input).value.strip(),
                "default_remote": str(self.query_one("#git-remote-type", Select).value),
                "token":          self.query_one("#git-token",     Input).value.strip(),
                "ssh_key_path":   self.query_one("#git-ssh-key",   Input).value.strip(),
            }
            save_global_config(cfg)
            self._update_tab_status("git-save-status", "✓ Saved")
            self.app.notify("Git settings saved.", severity="information")
        except Exception:
            log.exception("Failed to save git settings")
            self.app.notify("Failed to save — see log.", severity="error")

    # ── Save — Backup ─────────────────────────────────────────────────────────

    def _save_backup(self) -> None:
        try:
            cfg = load_global_config()
            cfg.setdefault("system_modules", {})["backup"] = {
                "enabled":   self.query_one("#backup-enabled",   Checkbox).value,
                "backend":   self.query_one("#backup-backend",   Input).value.strip(),
                "repo_path": self.query_one("#backup-repo",      Input).value.strip(),
                "password":  self.query_one("#backup-password",  Input).value.strip(),
                "paths":     self.query_one("#backup-paths",     Input).value.strip(),
                "schedule":  str(self.query_one("#backup-schedule", Select).value),
            }
            save_global_config(cfg)
            self._update_tab_status("backup-save-status", "✓ Saved")
            self.app.notify("Backup settings saved.", severity="information")
        except Exception:
            log.exception("Failed to save backup settings")
            self.app.notify("Failed to save — see log.", severity="error")

    # ── Save — Calendar ───────────────────────────────────────────────────────

    def _save_calendar(self) -> None:
        try:
            cfg = load_global_config()
            cfg.setdefault("system_modules", {})["calendar"] = {
                "data_path":       self.query_one("#cal-data-path",      Input).value.strip(),
                "caldav_enabled":  self.query_one("#cal-caldav-enabled", Checkbox).value,
                "caldav_url":      self.query_one("#cal-caldav-url",     Input).value.strip(),
                "caldav_user":     self.query_one("#cal-caldav-user",    Input).value.strip(),
                "caldav_password": self.query_one("#cal-caldav-password",Input).value.strip(),
            }
            save_global_config(cfg)
            self._update_tab_status("cal-save-status", "✓ Saved")
            self.app.notify("Calendar settings saved.", severity="information")
        except Exception:
            log.exception("Failed to save calendar settings")
            self.app.notify("Failed to save — see log.", severity="error")

    # ── Save — SDForge ────────────────────────────────────────────────────────

    def _save_sdforge(self) -> None:
        try:
            cfg = load_global_config()
            cfg.setdefault("system_modules", {})["sdforge"] = {
                "endpoint": self.query_one("#sdforge-endpoint", Input).value.strip(),
                "api_key":  self.query_one("#sdforge-api-key",  Input).value.strip(),
            }
            save_global_config(cfg)
            self._update_tab_status("sdforge-save-status", "✓ Saved")
            self.app.notify("SDForge settings saved.", severity="information")
        except Exception:
            log.exception("Failed to save SDForge settings")
            self.app.notify("Failed to save — see log.", severity="error")

    # ── Save — Server ─────────────────────────────────────────────────────────

    def _save_server(self) -> None:
        try:
            cfg = load_global_config()
            http_port  = int(self.query_one("#server-http-port",  Input).value.strip() or "80")
            https_port = int(self.query_one("#server-https-port", Input).value.strip() or "443")
            cfg.setdefault("system_modules", {})["server"] = {
                "web_root":   self.query_one("#server-web-root", Input).value.strip(),
                "http_port":  http_port,
                "https_port": https_port,
            }
            save_global_config(cfg)
            self._update_tab_status("server-save-status", "✓ Saved")
            self.app.notify("Server settings saved.", severity="information")
        except Exception:
            log.exception("Failed to save server settings")
            self.app.notify("Failed to save — see log.", severity="error")

    def _update_tab_status(self, label_id: str, text: str) -> None:
        try:
            lbl = self.query_one(f"#{label_id}", Label)
            lbl.update(text)
            lbl.set_classes("status-ok tab-save-status")
        except Exception:
            pass

    # ── Backup Now ────────────────────────────────────────────────────────────

    def _on_restic_modal_dismissed(self, result: bool) -> None:
        if result:
            try:
                self.query_one(TabbedContent).active = "tab_setup"
            except Exception:
                log.exception("Failed to switch to Setup tab")

    async def _do_system_backup(self) -> None:
        from modules.backup.backup_ops import restic_ensure_initialized, restic_backup
        import asyncio as _aio

        repo      = self.query_one("#backup-repo",      Input).value.strip()
        pw        = self.query_one("#backup-password",  Input).value.strip()
        paths_raw = self.query_one("#backup-paths",     Input).value.strip()
        paths     = [p.strip() for p in paths_raw.split(",") if p.strip()]

        if not repo:
            self.app.notify("Set a repository path first.", severity="warning")
            return
        if not paths:
            self.app.notify("Enter at least one path to back up.", severity="warning")
            return

        self.app.notify("Initialising repository if needed…", severity="information")
        loop = _aio.get_event_loop()
        ok, msg = await loop.run_in_executor(None, restic_ensure_initialized, repo, pw)
        if not ok:
            self.app.notify(f"Init failed — {msg[:140]}", severity="error")
            log.error("restic_ensure_initialized failed: %s", msg)
            return

        self.app.notify("Backup running…", severity="information")
        ok, out = await loop.run_in_executor(None, restic_backup, repo, pw, paths)
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

    def _maybe_run_install(self, pkg_id: str, cmd: str) -> None:
        if cmd.startswith("sudo ") and not _sudo.has():
            self.app.push_screen(
                SudoModal(),
                lambda pw: self._on_sudo_password(pw, pkg_id, cmd),
            )
        else:
            self.run_worker(self._run_install(pkg_id, cmd))

    def _on_sudo_password(self, password: str | None, pkg_id: str, cmd: str) -> None:
        if password is None:
            self.app.notify("Install cancelled — no password provided.", severity="warning")
            return
        _sudo.set_password(password)
        self.run_worker(self._run_install(pkg_id, cmd))

    async def _run_install(self, pkg_id: str, cmd: str) -> None:
        log_label = self.query_one("#setup-log", Label)
        cmd_to_run, stdin_data = _sudo.inject_shell(cmd)
        log_label.update(f"Running: {cmd_to_run}\n…")
        log.info("Setup install: %s", cmd_to_run)
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd_to_run,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await proc.communicate(input=stdin_data)
            output = stdout.decode(errors="replace").strip()
            if proc.returncode == 0:
                log_label.update(f"✓ {pkg_id} installed.\n{output[-300:]}")
                self.app.notify(f"{pkg_id} installed.", severity="information")
                label_id = f"#dep-status-{pkg_id.replace('-', '_')}"
                try:
                    lbl = self.query_one(label_id, Label)
                    lbl.update("✓ installed")
                    lbl.set_classes("dep-status-ok")
                except Exception:
                    pass
            else:
                log.warning("Install failed (exit %d): %s", proc.returncode, output[-300:])
                if "incorrect password" in output.lower() or "sorry, try again" in output.lower():
                    _sudo.clear()
                    log_label.update(f"✗ Wrong sudo password.\n{output[-300:]}")
                    self.app.notify(
                        "Wrong sudo password — click Install again to retry.",
                        severity="error",
                    )
                else:
                    log_label.update(f"✗ Install failed (exit {proc.returncode}).\n{output[-300:]}")
                    self.app.notify("Install failed — see log area.", severity="error")
        except Exception:
            log.exception("Install subprocess failed: %s", cmd_to_run)
            log_label.update("✗ Subprocess error — see nexus.log.")
            self.app.notify("Install error — see log.", severity="error")
