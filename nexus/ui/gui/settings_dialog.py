"""Settings dialog for the Nexus GUI — mirrors the TUI SettingsScreen tabs."""
from __future__ import annotations
import shutil
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTabWidget, QWidget, QLabel, QPushButton, QLineEdit, QComboBox,
    QGroupBox, QScrollArea, QFrame, QTextEdit, QListWidget, QListWidgetItem,
    QSizePolicy, QMessageBox, QInputDialog, QSplitter, QTableWidget,
    QTableWidgetItem, QHeaderView, QCheckBox,
)

_SETTINGS_ROOT = Path(__file__).parent.parent.parent.parent

from nexus.core.config_manager import load_global_config, save_global_config, mcp_servers as _mcp_servers
from nexus.core.logger import get
from nexus.ui.gui.theme import GUI_THEMES, GUI_THEME_LABELS, DEFAULT_GUI_THEME

log = get("ui.gui.settings_dialog")

_CAPABILITIES = [
    "reasoning", "coding", "embedding", "instruct",
    "function_calling", "vision", "stt_tts",
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


# ── Background workers ────────────────────────────────────────────────────────

class _VerifyWorker(QThread):
    result = Signal(bool, str)

    def __init__(self, api_key: str) -> None:
        super().__init__()
        self._key = api_key

    def run(self) -> None:
        try:
            import httpx
            r = httpx.get(
                "https://api.anthropic.com/v1/models",
                headers={"x-api-key": self._key, "anthropic-version": "2023-06-01"},
                timeout=10,
            )
            if r.status_code == 200:
                models = r.json().get("data", [])
                first = models[0]["id"] if models else "claude"
                self.result.emit(True, f"Valid ({first}).")
            else:
                self.result.emit(False, f"HTTP {r.status_code}: {r.text[:120]}")
        except Exception as exc:
            self.result.emit(False, str(exc))


class _TestOAIModelsWorker(QThread):
    """Test an OpenAI-compatible /v1/models endpoint (local, openwebui, openai_compat)."""
    result = Signal(bool, str)

    def __init__(self, base_url: str, api_key: str, path: str = "/v1/models") -> None:
        super().__init__()
        self._base = base_url.rstrip("/")
        self._key  = api_key
        self._path = path

    def run(self) -> None:
        try:
            import httpx
            headers = {"Authorization": f"Bearer {self._key}"} if self._key else {}
            r = httpx.get(f"{self._base}{self._path}", headers=headers, timeout=10)
            if r.status_code == 200:
                data  = r.json().get("data", [])
                first = data[0]["id"] if data else "no models"
                self.result.emit(True, f"Connected ({first}).")
            else:
                self.result.emit(False, f"HTTP {r.status_code}: {r.text[:120]}")
        except Exception as exc:
            self.result.emit(False, str(exc))


class _InstallWorker(QThread):
    line_ready = Signal(str)
    done       = Signal(int)

    def __init__(self, cmd: list[str]) -> None:
        super().__init__()
        self._cmd = cmd

    def run(self) -> None:
        import subprocess
        try:
            proc = subprocess.Popen(
                self._cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            if proc.stdout:
                for line in proc.stdout:
                    self.line_ready.emit(line.rstrip())
            proc.wait()
            self.done.emit(proc.returncode or 0)
        except Exception as exc:
            self.line_ready.emit(f"Error: {exc}")
            self.done.emit(1)


class _BackupNowWorker(QThread):
    line_ready = Signal(str)
    done       = Signal(bool, str)

    def __init__(self, repo: str, password: str, paths: list[str]) -> None:
        super().__init__()
        self._repo     = repo
        self._password = password
        self._paths    = paths

    def run(self) -> None:
        try:
            from modules.backup.backup_ops import restic_ensure_initialized, restic_backup
            self.line_ready.emit("Initialising repository if needed…")
            ok, msg = restic_ensure_initialized(self._repo, self._password)
            if not ok:
                self.done.emit(False, f"Init failed: {msg[:200]}")
                return
            self.line_ready.emit("Running backup…")
            ok, out = restic_backup(self._repo, self._password, self._paths)
            self.done.emit(ok, out[:200] if not ok else "Backup completed.")
        except Exception as exc:
            self.done.emit(False, str(exc))


# ── Ollama setup dialog ───────────────────────────────────────────────────────

class _OllamaSetupDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ollama Setup")
        self.setMinimumWidth(480)
        self._worker: QThread | None = None
        self._build()

    def _build(self) -> None:
        import platform as _plat
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Architecture: {_plat.machine()}"))
        layout.addWidget(QLabel("Install command:"))
        cmd_lbl = QLabel("curl -fsSL https://ollama.com/install.sh | sh")
        cmd_lbl.setObjectName("dim")
        layout.addWidget(cmd_lbl)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(100)
        layout.addWidget(self._log)
        btn_row = QHBoxLayout()
        self._install_btn = QPushButton("Run Install")
        self._install_btn.clicked.connect(self._run_install)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._install_btn)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _run_install(self) -> None:
        self._install_btn.setEnabled(False)
        self._worker = _InstallWorker(["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"])
        self._worker.line_ready.connect(self._log.append)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, rc: int) -> None:
        if rc == 0:
            self._log.append("✓ Ollama installed successfully.")
            QMessageBox.information(self, "Done",
                                    "Ollama installed.\nSet the endpoint in AI Config → Local.")
            self.accept()
        else:
            self._log.append(f"✗ Install failed (exit {rc}).")
            self._install_btn.setEnabled(True)


# ── Dependency list (mirrors TUI _MODULE_DEPS) ───────────────────────────────

_DEPS: list[tuple[str, str, str | None, str | None]] = [
    ("System",    "xclip (X11 clipboard)",          "xclip",              None),
    ("System",    "wl-clipboard (Wayland)",          "wl-clipboard",       None),
    ("Git",       "Git",                             "git",                None),
    ("Web",       "Node.js",                         "nodejs",             None),
    ("Web",       "npm",                             "npm",                None),
    ("Research",  "ripgrep (rg)",                    "ripgrep",            None),
    ("Research",  "pandoc (PDF export)",             "pandoc",             None),
    ("Research",  "xelatex (pandoc PDF engine)",     "texlive-xetex",      None),
    ("Codex",     "ripgrep (rg)",                    "ripgrep",            None),
    ("Journal",   "pdflatex",                        "texlive-latex-base", None),
    ("Streaming", "OBS Studio",                      "obs-studio",         None),
    ("Emulator",  "RetroArch",                       "retroarch",          None),
    ("Vault",     "GnuPG",                           "gnupg",              None),
    ("Vault",     "age",                             "age",                None),
    ("Vault",     "KeePassXC",                       "keepassxc",          None),
    ("Vault",     "cryptsetup",                      "cryptsetup",         None),
    ("Server",    "Docker",                          "docker.io",          None),
    ("Backup",    "restic",                          "restic",             None),
    ("LocalAI",   "Ollama",                          None, "curl -fsSL https://ollama.com/install.sh | sh"),
    ("Security",  "ufw",                             "ufw",                None),
    ("Security",  "nmap",                            "nmap",               None),
    ("Security",  "fail2ban",                        "fail2ban",           None),
    ("YouTube",   "ffmpeg",                          "ffmpeg",             None),
]

_DEP_BINARY: dict[str, str] = {
    "xclip (X11 clipboard)":      "xclip",
    "wl-clipboard (Wayland)":     "wl-paste",
    "Git":                        "git",
    "Node.js":                    "node",
    "npm":                        "npm",
    "ripgrep (rg)":               "rg",
    "pandoc (PDF export)":        "pandoc",
    "xelatex (pandoc PDF engine)":"xelatex",
    "pdflatex":                   "pdflatex",
    "OBS Studio":                 "obs",
    "RetroArch":                  "retroarch",
    "GnuPG":                      "gpg",
    "age":                        "age",
    "KeePassXC":                  "keepassxc-cli",
    "cryptsetup":                 "cryptsetup",
    "Docker":                     "docker",
    "restic":                     "restic",
    "Ollama":                     "ollama",
    "ufw":                        "ufw",
    "nmap":                       "nmap",
    "fail2ban":                   "fail2ban-client",
    "ffmpeg":                     "ffmpeg",
}


# ── AI Config tab ─────────────────────────────────────────────────────────────

class _AITab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._worker: QThread | None = None
        self._cap_widgets: dict[str, tuple[QCheckBox, QLineEdit]] = {}
        self._provider   = "anthropic"
        self._model_mode = "basic"
        self._build()

    def _build(self) -> None:  # noqa: C901
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        cfg  = load_global_config()
        ai   = cfg.get("ai", {})
        prov = ai.get("provider", "anthropic")
        if prov in ("api_key", "anthropic"):
            prov = "anthropic"
        if prov not in ("anthropic", "openwebui", "openai_compat", "local"):
            prov = "anthropic"
        self._provider   = prov
        self._model_mode = ai.get("model_mode", "basic")
        if self._model_mode not in ("basic", "advanced"):
            self._model_mode = "basic"

        pcfg    = ai.get("providers", {})
        api_key = pcfg.get("anthropic", {}).get("api_key") or ai.get("api_key", "")
        loc_ep  = pcfg.get("local", {}).get("endpoint") or ai.get("local_endpoint", "http://localhost:11434")
        loc_mod = pcfg.get("local", {}).get("model") or ai.get("local_model", "")
        ow_url  = pcfg.get("openwebui", {}).get("base_url", "http://localhost:3000")
        ow_key  = pcfg.get("openwebui", {}).get("api_key", "")
        ow_mod  = pcfg.get("openwebui", {}).get("model", "")
        oa_url  = pcfg.get("openai_compat", {}).get("base_url", "")
        oa_key  = pcfg.get("openai_compat", {}).get("api_key", "")
        oa_mod  = pcfg.get("openai_compat", {}).get("model", "")
        b_model = ai.get("model", "")
        models  = ai.get("models", {})

        # ── Provider bar ──────────────────────────────────────────────────────
        prov_box = QGroupBox("AI Provider")
        prov_lay = QHBoxLayout(prov_box)
        self._btn_anthropic     = QPushButton("Anthropic")
        self._btn_openwebui     = QPushButton("OpenWebUI")
        self._btn_openai_compat = QPushButton("OpenAI-compat")
        self._btn_local         = QPushButton("Local")
        for btn in (self._btn_anthropic, self._btn_openwebui,
                    self._btn_openai_compat, self._btn_local):
            btn.setCheckable(True)
            prov_lay.addWidget(btn)
        prov_lay.addStretch()
        self._btn_anthropic.clicked.connect(lambda: self._set_provider("anthropic"))
        self._btn_openwebui.clicked.connect(lambda: self._set_provider("openwebui"))
        self._btn_openai_compat.clicked.connect(lambda: self._set_provider("openai_compat"))
        self._btn_local.clicked.connect(lambda: self._set_provider("local"))

        self._adv_btn = QPushButton("Advanced ▾")
        self._adv_btn.setCheckable(True)
        self._adv_btn.setChecked(self._model_mode == "advanced")
        self._adv_btn.setFixedHeight(32)
        self._adv_btn.setStyleSheet(
            "QPushButton { background: #B45AFF; color: #1A0A2E; font-weight: bold;"
            " border-radius: 4px; padding: 4px 12px; }"
            "QPushButton:checked { background: #8A2BE2; color: #E0D0FF; }"
            "QPushButton:hover   { background: #C870FF; }"
        )
        self._adv_btn.clicked.connect(self._toggle_advanced)
        prov_lay.addWidget(self._adv_btn)
        layout.addWidget(prov_box)

        # ── Scrollable provider sections ──────────────────────────────────────
        scroll  = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        cl      = QVBoxLayout(content)
        cl.setSpacing(8)

        # Anthropic
        self._api_group = QGroupBox("Anthropic API Key")
        ag = QFormLayout(self._api_group)
        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.Password)
        self._api_key_input.setText(api_key)
        self._api_key_input.setPlaceholderText("sk-ant-…")
        ag.addRow("API Key:", self._api_key_input)
        vrow = QHBoxLayout()
        self._verify_btn    = QPushButton("Verify")
        self._verify_status = QLabel("—")
        self._verify_status.setObjectName("dim")
        self._verify_btn.clicked.connect(self._verify)
        vrow.addWidget(self._verify_btn); vrow.addWidget(self._verify_status); vrow.addStretch()
        ag.addRow("", vrow)
        hint = QLabel("Stored in config/settings.yaml (git-ignored).")
        hint.setObjectName("dim")
        ag.addRow("", hint)
        cl.addWidget(self._api_group)

        # OpenWebUI
        self._openwebui_group = QGroupBox("OpenWebUI")
        og = QFormLayout(self._openwebui_group)
        self._ow_url = QLineEdit(); self._ow_url.setPlaceholderText("http://localhost:3000"); self._ow_url.setText(ow_url)
        og.addRow("Base URL:", self._ow_url)
        self._ow_key = QLineEdit(); self._ow_key.setEchoMode(QLineEdit.Password); self._ow_key.setPlaceholderText("sk-…"); self._ow_key.setText(ow_key)
        og.addRow("API Key:", self._ow_key)
        self._ow_model = QLineEdit(); self._ow_model.setPlaceholderText("llama3.2"); self._ow_model.setText(ow_mod)
        og.addRow("Model:", self._ow_model)
        ow_row = QHBoxLayout()
        self._ow_test_btn    = QPushButton("Test Connection")
        self._ow_test_status = QLabel("—"); self._ow_test_status.setObjectName("dim")
        self._ow_test_btn.clicked.connect(self._test_openwebui)
        ow_row.addWidget(self._ow_test_btn); ow_row.addWidget(self._ow_test_status); ow_row.addStretch()
        og.addRow("", ow_row)
        cl.addWidget(self._openwebui_group)

        # OpenAI-compat
        self._openai_compat_group = QGroupBox("OpenAI-Compatible Endpoint")
        oag = QFormLayout(self._openai_compat_group)
        self._oa_url = QLineEdit(); self._oa_url.setPlaceholderText("http://localhost:8000"); self._oa_url.setText(oa_url)
        oag.addRow("Base URL:", self._oa_url)
        self._oa_key = QLineEdit(); self._oa_key.setEchoMode(QLineEdit.Password); self._oa_key.setPlaceholderText("sk-…"); self._oa_key.setText(oa_key)
        oag.addRow("API Key:", self._oa_key)
        self._oa_model = QLineEdit(); self._oa_model.setPlaceholderText("gpt-4o"); self._oa_model.setText(oa_mod)
        oag.addRow("Model:", self._oa_model)
        oa_row = QHBoxLayout()
        self._oa_test_btn    = QPushButton("Test Connection")
        self._oa_test_status = QLabel("—"); self._oa_test_status.setObjectName("dim")
        self._oa_test_btn.clicked.connect(self._test_openai_compat)
        oa_row.addWidget(self._oa_test_btn); oa_row.addWidget(self._oa_test_status); oa_row.addStretch()
        oag.addRow("", oa_row)
        cl.addWidget(self._openai_compat_group)

        # Local
        self._local_group = QGroupBox("Local Model (Ollama / LM Studio / llama.cpp)")
        lg = QFormLayout(self._local_group)
        self._local_endpoint = QLineEdit(); self._local_endpoint.setPlaceholderText("http://localhost:11434"); self._local_endpoint.setText(loc_ep)
        lg.addRow("Endpoint:", self._local_endpoint)
        self._local_model_inp = QLineEdit(); self._local_model_inp.setPlaceholderText("llama3.2"); self._local_model_inp.setText(loc_mod)
        lg.addRow("Model:", self._local_model_inp)
        lt_row = QHBoxLayout()
        self._lt_test_btn    = QPushButton("Test Connection")
        self._lt_test_status = QLabel("—"); self._lt_test_status.setObjectName("dim")
        self._lt_test_btn.clicked.connect(self._test_local)
        lt_row.addWidget(self._lt_test_btn); lt_row.addWidget(self._lt_test_status); lt_row.addStretch()
        lg.addRow("", lt_row)
        ollama_row = QHBoxLayout()
        ollama_btn = QPushButton("Ollama Setup →")
        ollama_btn.clicked.connect(self._ollama_setup)
        ollama_row.addWidget(ollama_btn)
        ollama_hint = QLabel("Install Ollama if not already present.")
        ollama_hint.setObjectName("dim")
        ollama_row.addWidget(ollama_hint)
        ollama_row.addStretch()
        lg.addRow("", ollama_row)
        cl.addWidget(self._local_group)

        # Model section (Basic / Advanced toggle)
        self._model_group = QGroupBox("Model")
        ml = QVBoxLayout(self._model_group)

        self._model_basic_widget = QWidget()
        bf = QFormLayout(self._model_basic_widget)
        self._basic_model = QLineEdit()
        self._basic_model.setPlaceholderText("claude-sonnet-4-6")
        self._basic_model.setText(b_model)
        bf.addRow("Model name:", self._basic_model)
        ml.addWidget(self._model_basic_widget)

        self._model_adv_widget = QWidget()
        af = QVBoxLayout(self._model_adv_widget)
        for cap in _CAPABILITIES:
            cap_cfg = models.get(cap, {})
            row_w   = QWidget()
            row_lay = QHBoxLayout(row_w)
            row_lay.setContentsMargins(0, 0, 0, 0)
            cb  = QCheckBox()
            cb.setChecked(cap_cfg.get("enabled", True))
            inp = QLineEdit()
            inp.setPlaceholderText("model name…")
            inp.setText(cap_cfg.get("model", ""))
            inp.setEnabled(cb.isChecked())
            cb.toggled.connect(inp.setEnabled)
            lbl = QLabel(_CAP_LABELS[cap])
            lbl.setFixedWidth(130)
            row_lay.addWidget(cb)
            row_lay.addWidget(lbl)
            row_lay.addWidget(inp)
            af.addWidget(row_w)
            self._cap_widgets[cap] = (cb, inp)
        ml.addWidget(self._model_adv_widget)
        cl.addWidget(self._model_group)

        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        save_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._save)
        save_row.addStretch()
        save_row.addWidget(save_btn)
        layout.addLayout(save_row)

        self._set_provider(self._provider)
        self._update_model_mode()

    # ── Provider / mode visibility ────────────────────────────────────────────

    def _set_provider(self, provider: str) -> None:
        self._provider = provider
        self._btn_anthropic.setChecked(provider == "anthropic")
        self._btn_openwebui.setChecked(provider == "openwebui")
        self._btn_openai_compat.setChecked(provider == "openai_compat")
        self._btn_local.setChecked(provider == "local")
        self._api_group.setVisible(provider == "anthropic")
        self._openwebui_group.setVisible(provider == "openwebui")
        self._openai_compat_group.setVisible(provider == "openai_compat")
        self._local_group.setVisible(provider == "local")

    def _toggle_advanced(self) -> None:
        self._model_mode = "advanced" if self._adv_btn.isChecked() else "basic"
        self._adv_btn.setText("Basic ▴" if self._model_mode == "advanced" else "Advanced ▾")
        self._update_model_mode()

    def _update_model_mode(self) -> None:
        self._model_basic_widget.setVisible(self._model_mode == "basic")
        self._model_adv_widget.setVisible(self._model_mode == "advanced")

    # ── Connection tests ──────────────────────────────────────────────────────

    def _verify(self) -> None:
        key = self._api_key_input.text().strip()
        if not key:
            self._verify_status.setText("Enter a key first.")
            return
        self._verify_btn.setEnabled(False)
        self._verify_status.setText("Verifying…")
        self._worker = _VerifyWorker(key)
        self._worker.result.connect(self._on_verify)
        self._worker.start()

    def _on_verify(self, ok: bool, msg: str) -> None:
        self._verify_status.setText(f"{'✓' if ok else '✗'} {msg}")
        self._verify_btn.setEnabled(True)
        self._worker = None

    def _test_openwebui(self) -> None:
        url = self._ow_url.text().strip()
        if not url:
            self._ow_test_status.setText("Fill URL first.")
            return
        self._ow_test_btn.setEnabled(False)
        self._ow_test_status.setText("Testing…")
        self._worker = _TestOAIModelsWorker(url, self._ow_key.text().strip(), "/api/v1/models")
        self._worker.result.connect(self._on_test_ow)
        self._worker.start()

    def _on_test_ow(self, ok: bool, msg: str) -> None:
        self._ow_test_status.setText(f"{'✓' if ok else '✗'} {msg}")
        self._ow_test_btn.setEnabled(True)
        self._worker = None

    def _test_openai_compat(self) -> None:
        url = self._oa_url.text().strip()
        if not url:
            self._oa_test_status.setText("Fill URL first.")
            return
        self._oa_test_btn.setEnabled(False)
        self._oa_test_status.setText("Testing…")
        self._worker = _TestOAIModelsWorker(url, self._oa_key.text().strip())
        self._worker.result.connect(self._on_test_oa)
        self._worker.start()

    def _on_test_oa(self, ok: bool, msg: str) -> None:
        self._oa_test_status.setText(f"{'✓' if ok else '✗'} {msg}")
        self._oa_test_btn.setEnabled(True)
        self._worker = None

    def _test_local(self) -> None:
        ep = self._local_endpoint.text().strip()
        if not ep:
            self._lt_test_status.setText("Fill endpoint first.")
            return
        self._lt_test_btn.setEnabled(False)
        self._lt_test_status.setText("Testing…")
        self._worker = _TestOAIModelsWorker(ep, "")
        self._worker.result.connect(self._on_test_local)
        self._worker.start()

    def _on_test_local(self, ok: bool, msg: str) -> None:
        self._lt_test_status.setText(f"{'✓' if ok else '✗'} {msg}")
        self._lt_test_btn.setEnabled(True)
        self._worker = None

    def _ollama_setup(self) -> None:
        if shutil.which("ollama"):
            QMessageBox.information(self, "Ollama", "Ollama is already installed.")
            return
        _OllamaSetupDialog(self).exec()

    # ── Save ──────────────────────────────────────────────────────────────────

    def _save(self) -> None:
        cfg = load_global_config()
        ai  = cfg.setdefault("ai", {})
        ai["provider"]   = self._provider
        ai["model_mode"] = self._model_mode
        providers        = ai.setdefault("providers", {})

        if self._provider == "anthropic":
            providers.setdefault("anthropic", {})["api_key"] = self._api_key_input.text().strip()
        elif self._provider == "openwebui":
            providers["openwebui"] = {
                "base_url": self._ow_url.text().strip(),
                "api_key":  self._ow_key.text().strip(),
                "model":    self._ow_model.text().strip(),
            }
        elif self._provider == "openai_compat":
            providers["openai_compat"] = {
                "base_url": self._oa_url.text().strip(),
                "api_key":  self._oa_key.text().strip(),
                "model":    self._oa_model.text().strip(),
            }
        elif self._provider == "local":
            providers["local"] = {
                "endpoint": self._local_endpoint.text().strip(),
                "model":    self._local_model_inp.text().strip(),
            }

        if self._model_mode == "basic":
            ai["model"] = self._basic_model.text().strip()
        else:
            m = ai.setdefault("models", {})
            for cap in _CAPABILITIES:
                cb, inp = self._cap_widgets[cap]
                m[cap] = {"enabled": cb.isChecked(), "model": inp.text().strip()}

        save_global_config(cfg)
        QMessageBox.information(self, "Saved", "AI settings saved.")


# ── Appearance tab ────────────────────────────────────────────────────────────

class _AppearanceTab(QWidget):
    theme_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        cfg     = load_global_config()
        current = cfg.get("ui", {}).get("gui_theme", DEFAULT_GUI_THEME)

        group   = QGroupBox("GUI Colour Theme")
        grp_lay = QVBoxLayout(group)

        self._combo = QComboBox()
        for key, label in GUI_THEME_LABELS.items():
            self._combo.addItem(label, userData=key)
            if key == current:
                self._combo.setCurrentIndex(self._combo.count() - 1)
        grp_lay.addWidget(self._combo)

        self._swatch = QFrame()
        self._swatch.setFixedHeight(32)
        self._swatch.setFrameShape(QFrame.StyledPanel)
        grp_lay.addWidget(self._swatch)

        self._combo.currentIndexChanged.connect(self._preview)
        self._preview()

        layout.addWidget(group)
        layout.addStretch()

        note = QLabel("Changes apply immediately when saved.")
        note.setObjectName("dim")
        layout.addWidget(note)

        save_row = QHBoxLayout()
        save_btn = QPushButton("Apply & Save")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._save)
        save_row.addStretch()
        save_row.addWidget(save_btn)
        layout.addLayout(save_row)

    def _preview(self) -> None:
        name = self._combo.currentData()
        qss  = GUI_THEMES.get(name, "")
        bg   = "#1A0A2E"
        for line in qss.splitlines():
            if "background-color:" in line and bg == "#1A0A2E":
                parts = line.split("background-color:")
                if len(parts) > 1:
                    bg = parts[1].strip().rstrip(";").strip()
                    break
        self._swatch.setStyleSheet(f"background: {bg}; border-radius: 4px;")

    def _save(self) -> None:
        name = self._combo.currentData()
        cfg  = load_global_config()
        cfg.setdefault("ui", {})["gui_theme"] = name
        save_global_config(cfg)
        self.theme_changed.emit(name)


# ── Setup tab ─────────────────────────────────────────────────────────────────

class _SetupTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._workers: list[QThread] = []
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        scroll   = QScrollArea()
        scroll.setWidgetResizable(True)
        content  = QWidget()
        cl       = QVBoxLayout(content)
        cl.setSpacing(4)

        last_group = ""
        for group, name, apt_pkg, special in _DEPS:
            if group != last_group:
                lbl = QLabel(f"── {group} ──")
                lbl.setObjectName("subtitle")
                cl.addWidget(lbl)
                last_group = group
            binary    = _DEP_BINARY.get(name, name.split()[0].lower())
            installed = shutil.which(binary) is not None
            row = _DepRow(name, installed, apt_pkg, special)
            row.install_requested.connect(self._install)
            cl.addWidget(row)

        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(120)
        layout.addWidget(self._log)

    def _install(self, cmd: list[str]) -> None:
        worker = _InstallWorker(cmd)
        worker.line_ready.connect(self._log.append)
        worker.done.connect(lambda rc: self._log.append(
            f"✓ Done (exit {rc})" if rc == 0 else f"✗ Failed (exit {rc})"
        ))
        self._workers.append(worker)
        worker.start()


class _DepRow(QWidget):
    install_requested = Signal(list)

    def __init__(self, name: str, installed: bool, apt_pkg: str | None, special: str | None) -> None:
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(4, 2, 4, 2)

        status = QLabel("✓" if installed else "✗")
        status.setStyleSheet("color: #00FF88;" if installed else "color: #FF4444;")
        status.setFixedWidth(20)
        row.addWidget(status)

        lbl = QLabel(name)
        row.addWidget(lbl, 1)

        if not installed and (apt_pkg or special):
            btn = QPushButton("Install")
            btn.setFixedWidth(80)
            btn.clicked.connect(lambda: self._do_install(apt_pkg, special))
            row.addWidget(btn)

    def _do_install(self, apt_pkg: str | None, special: str | None) -> None:
        if special:
            import shlex
            self.install_requested.emit(shlex.split(special))
        elif apt_pkg:
            self.install_requested.emit(["sudo", "apt-get", "install", "-y", apt_pkg])


# ── MCP Servers tab ───────────────────────────────────────────────────────────

class _MCPTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected_sid: str | None = None
        self._build()

    def _build(self) -> None:
        from nexus.ai.mcp_registry import REGISTRY as MCP_REGISTRY
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        top_splitter = QSplitter(Qt.Horizontal)

        left     = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setSpacing(4)
        self._summary_lbl = QLabel("0 servers active")
        self._summary_lbl.setObjectName("subtitle")
        left_lay.addWidget(self._summary_lbl)
        self._active_list = QListWidget()
        self._active_list.currentItemChanged.connect(self._on_active_selected)
        left_lay.addWidget(self._active_list)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_server)
        left_lay.addWidget(remove_btn)
        top_splitter.addWidget(left)

        right     = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.addWidget(QLabel("Available Servers (double-click to add)"))
        self._catalog_list = QListWidget()
        for spec in MCP_REGISTRY:
            item = QListWidgetItem(f"{spec.name}  —  {spec.description[:60]}")
            item.setData(Qt.UserRole, spec)
            self._catalog_list.addItem(item)
        self._catalog_list.itemDoubleClicked.connect(self._add_server)
        right_lay.addWidget(self._catalog_list)
        top_splitter.addWidget(right)

        top_splitter.setSizes([380, 380])
        layout.addWidget(top_splitter, 1)

        self._detail_group = QGroupBox("Edit Server Configuration")
        self._detail_group.setVisible(False)
        dl = QVBoxLayout(self._detail_group)
        dl.setSpacing(6)

        df = QFormLayout()
        self._edit_command = QLineEdit(); self._edit_command.setPlaceholderText("e.g. npx")
        df.addRow("Command:", self._edit_command)
        self._edit_args = QLineEdit(); self._edit_args.setPlaceholderText("space-separated arguments")
        df.addRow("Args:", self._edit_args)
        dl.addLayout(df)

        env_lbl = QLabel("Environment Variables:")
        env_lbl.setObjectName("subtitle")
        dl.addWidget(env_lbl)
        self._env_table = QTableWidget(0, 2)
        self._env_table.setHorizontalHeaderLabels(["Key", "Value"])
        self._env_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._env_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._env_table.setMaximumHeight(140)
        dl.addWidget(self._env_table)

        env_btn_row = QHBoxLayout()
        add_env_btn = QPushButton("+ Row"); add_env_btn.clicked.connect(self._add_env_row)
        del_env_btn = QPushButton("− Row"); del_env_btn.clicked.connect(self._del_env_row)
        env_btn_row.addWidget(add_env_btn); env_btn_row.addWidget(del_env_btn); env_btn_row.addStretch()
        dl.addLayout(env_btn_row)

        sr = QHBoxLayout()
        se = QPushButton("Save Changes"); se.setObjectName("primary"); se.clicked.connect(self._save_server_edit)
        sr.addStretch(); sr.addWidget(se)
        dl.addLayout(sr)
        layout.addWidget(self._detail_group)
        self._refresh_active()

    def _refresh_active(self) -> None:
        self._active_list.clear()
        cfg     = load_global_config()
        servers = _mcp_servers(cfg)
        for sid, scfg in servers.items():
            args_preview = " ".join(scfg.get("args", []))[:40]
            item = QListWidgetItem(f"{sid}  —  {scfg.get('command', '')} {args_preview}")
            item.setData(Qt.UserRole, sid)
            self._active_list.addItem(item)
        n = len(servers)
        self._summary_lbl.setText(f"{n} server{'s' if n != 1 else ''} active")
        if self._selected_sid and self._selected_sid not in servers:
            self._detail_group.setVisible(False)
            self._selected_sid = None

    def _on_active_selected(self, current: QListWidgetItem | None, _prev) -> None:
        if current is None:
            self._detail_group.setVisible(False); self._selected_sid = None; return
        sid = current.data(Qt.UserRole)
        self._selected_sid = sid
        scfg = _mcp_servers(load_global_config()).get(sid, {})
        self._edit_command.setText(scfg.get("command", ""))
        self._edit_args.setText(" ".join(scfg.get("args", [])))
        env = scfg.get("env", {})
        self._env_table.setRowCount(0)
        for k, v in env.items():
            row = self._env_table.rowCount(); self._env_table.insertRow(row)
            self._env_table.setItem(row, 0, QTableWidgetItem(k))
            self._env_table.setItem(row, 1, QTableWidgetItem(str(v)))
        self._detail_group.setVisible(True)
        self._detail_group.setTitle(f"Edit — {sid}")

    def _add_env_row(self) -> None:
        r = self._env_table.rowCount(); self._env_table.insertRow(r)
        self._env_table.setItem(r, 0, QTableWidgetItem(""))
        self._env_table.setItem(r, 1, QTableWidgetItem(""))

    def _del_env_row(self) -> None:
        r = self._env_table.currentRow()
        if r >= 0: self._env_table.removeRow(r)

    def _save_server_edit(self) -> None:
        if not self._selected_sid: return
        import shlex
        cfg  = load_global_config()
        scfg = _mcp_servers(cfg).get(self._selected_sid)
        if scfg is None: return
        scfg["command"] = self._edit_command.text().strip()
        args_text = self._edit_args.text().strip()
        scfg["args"] = shlex.split(args_text) if args_text else []
        env: dict[str, str] = {}
        for row in range(self._env_table.rowCount()):
            ki = self._env_table.item(row, 0); vi = self._env_table.item(row, 1)
            k = (ki.text().strip() if ki else ""); v = (vi.text().strip() if vi else "")
            if k: env[k] = v
        scfg["env"] = env
        save_global_config(cfg)
        self._refresh_active()
        QMessageBox.information(self, "Saved", f"Server '{self._selected_sid}' updated.")

    def _add_server(self, item: QListWidgetItem) -> None:
        from nexus.ai.mcp_registry import MCPServerSpec
        spec: MCPServerSpec = item.data(Qt.UserRole)
        env_vals: dict[str, str] = {}
        for key in spec.required_env:
            val, ok = QInputDialog.getText(self, f"Configure {spec.name}", f"{key}:")
            if not ok: return
            env_vals[key] = val
        cfg = load_global_config()
        server_cfg = spec.default_config()
        server_cfg["env"].update(env_vals)
        cfg.setdefault("mcp", {}).setdefault("servers", {})[spec.id] = server_cfg
        save_global_config(cfg)
        self._refresh_active()

    def _remove_server(self) -> None:
        item = self._active_list.currentItem()
        if not item: return
        sid = item.data(Qt.UserRole)
        cfg = load_global_config()
        _mcp_servers(cfg).pop(sid, None)
        save_global_config(cfg)
        self._refresh_active()


# ── General tab ───────────────────────────────────────────────────────────────

class _GeneralTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        cfg    = load_global_config()
        ai_cfg = cfg.get("ai", {})

        group = QGroupBox("Defaults")
        form  = QFormLayout(group)

        self._panel_combo = QComboBox()
        _panel_opts = [("Local AI", "local"), ("Claude Code CLI", "claude_code"), ("Shell", "shell")]
        _panel_val  = ai_cfg.get("default_panel", "local")
        if _panel_val not in {v for _, v in _panel_opts}:
            _panel_val = "local"
        for label, val in _panel_opts:
            self._panel_combo.addItem(label, userData=val)
            if val == _panel_val:
                self._panel_combo.setCurrentIndex(self._panel_combo.count() - 1)
        form.addRow("Default Input Panel:", self._panel_combo)
        layout.addWidget(group)

        info_group = QGroupBox("Info")
        info_lay   = QFormLayout(info_group)
        log_row = QHBoxLayout()
        log_row.addWidget(QLabel("logs/nexus.log"))
        open_log_btn = QPushButton("Open Folder")
        open_log_btn.clicked.connect(self._open_log_folder)
        log_row.addWidget(open_log_btn)
        log_row.addStretch()
        info_lay.addRow("Log file:", log_row)
        layout.addWidget(info_group)

        layout.addStretch()

        save_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._save)
        save_row.addStretch()
        save_row.addWidget(save_btn)
        layout.addLayout(save_row)

    def _save(self) -> None:
        cfg = load_global_config()
        cfg.setdefault("ai", {})["default_panel"] = self._panel_combo.currentData()
        save_global_config(cfg)
        QMessageBox.information(self, "Saved", "General settings saved.")

    def _open_log_folder(self) -> None:
        from nexus.core.platform import launch
        log_dir = _SETTINGS_ROOT / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        launch(str(log_dir))


# ── Git tab ───────────────────────────────────────────────────────────────────

class _GitTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        sys_cfg = load_global_config().get("system_modules", {})
        git_cfg = sys_cfg.get("git", {})

        hint = QLabel("Global Git identity used by Integrated-mode projects.")
        hint.setObjectName("dim")
        layout.addWidget(hint)

        group = QGroupBox("Git Identity")
        form  = QFormLayout(group)

        self._user_name = QLineEdit()
        self._user_name.setPlaceholderText("Your Name")
        self._user_name.setText(git_cfg.get("user_name", ""))
        form.addRow("User name:", self._user_name)

        self._user_email = QLineEdit()
        self._user_email.setPlaceholderText("you@example.com")
        self._user_email.setText(git_cfg.get("user_email", ""))
        form.addRow("User email:", self._user_email)

        self._remote_combo = QComboBox()
        for label, val in [("HTTPS", "https"), ("SSH", "ssh")]:
            self._remote_combo.addItem(label, userData=val)
            if val == git_cfg.get("default_remote", "https"):
                self._remote_combo.setCurrentIndex(self._remote_combo.count() - 1)
        form.addRow("Default remote:", self._remote_combo)

        self._token = QLineEdit()
        self._token.setEchoMode(QLineEdit.Password)
        self._token.setPlaceholderText("ghp_…")
        self._token.setText(git_cfg.get("token", ""))
        form.addRow("Access token (HTTPS):", self._token)

        self._ssh_key = QLineEdit()
        self._ssh_key.setPlaceholderText("~/.ssh/id_ed25519")
        self._ssh_key.setText(git_cfg.get("ssh_key_path", ""))
        form.addRow("SSH key path:", self._ssh_key)

        layout.addWidget(group)
        layout.addStretch()

        save_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._save)
        self._status = QLabel("")
        self._status.setObjectName("dim")
        save_row.addStretch()
        save_row.addWidget(self._status)
        save_row.addWidget(save_btn)
        layout.addLayout(save_row)

    def _save(self) -> None:
        cfg = load_global_config()
        cfg.setdefault("system_modules", {})["git"] = {
            "user_name":      self._user_name.text().strip(),
            "user_email":     self._user_email.text().strip(),
            "default_remote": self._remote_combo.currentData(),
            "token":          self._token.text().strip(),
            "ssh_key_path":   self._ssh_key.text().strip(),
        }
        save_global_config(cfg)
        self._status.setText("✓ Saved")


# ── Backup tab ────────────────────────────────────────────────────────────────

class _BackupTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._workers: list[QThread] = []
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        sys_cfg    = load_global_config().get("system_modules", {})
        backup_cfg = sys_cfg.get("backup", {})

        hint = QLabel("Automated backup for Nexus projects and data via restic.")
        hint.setObjectName("dim")
        layout.addWidget(hint)

        group = QGroupBox("Backup Configuration")
        form  = QFormLayout(group)

        self._enabled = QCheckBox("Enable automated backups")
        self._enabled.setChecked(backup_cfg.get("enabled", False))
        form.addRow("", self._enabled)

        _last     = backup_cfg.get("last_run")
        _last_str = _last[:16].replace("T", " ") if _last else "Never"
        form.addRow("Last backup:", QLabel(_last_str))

        self._backend = QLineEdit()
        self._backend.setPlaceholderText("local")
        self._backend.setText(backup_cfg.get("backend", "local"))
        form.addRow("Backend:", self._backend)

        self._repo = QLineEdit()
        self._repo.setPlaceholderText("/path/to/backup/repo")
        self._repo.setText(backup_cfg.get("repo_path", ""))
        form.addRow("Repository path:", self._repo)

        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.Password)
        self._password.setPlaceholderText("strong-passphrase")
        self._password.setText(backup_cfg.get("password", ""))
        form.addRow("Password:", self._password)

        self._paths = QLineEdit()
        self._paths.setPlaceholderText("~/nexus/projects, ~/documents")
        self._paths.setText(backup_cfg.get("paths", ""))
        form.addRow("Paths to back up:", self._paths)

        self._schedule = QComboBox()
        for label, val in [("Manual", "manual"), ("Daily", "daily"), ("Weekly", "weekly")]:
            self._schedule.addItem(label, userData=val)
            if val == backup_cfg.get("schedule", "manual"):
                self._schedule.setCurrentIndex(self._schedule.count() - 1)
        form.addRow("Schedule:", self._schedule)

        layout.addWidget(group)

        btn_row = QHBoxLayout()
        backup_now_btn = QPushButton("Backup Now")
        backup_now_btn.clicked.connect(self._backup_now)
        btn_row.addWidget(backup_now_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(80)
        layout.addWidget(self._log)

        save_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._save)
        self._status = QLabel("")
        self._status.setObjectName("dim")
        save_row.addStretch()
        save_row.addWidget(self._status)
        save_row.addWidget(save_btn)
        layout.addLayout(save_row)

    def _backup_now(self) -> None:
        if not shutil.which("restic"):
            QMessageBox.warning(self, "restic not installed",
                                "restic is not installed.\nGo to the Setup tab to install it.")
            return
        repo   = self._repo.text().strip()
        pw     = self._password.text().strip()
        paths  = [p.strip() for p in self._paths.text().split(",") if p.strip()]
        if not repo:
            QMessageBox.warning(self, "Missing", "Set a repository path first.")
            return
        if not paths:
            QMessageBox.warning(self, "Missing", "Enter at least one path to back up.")
            return
        self._log.clear()
        worker = _BackupNowWorker(repo, pw, paths)
        worker.line_ready.connect(self._log.append)
        worker.done.connect(self._on_backup_done)
        self._workers.append(worker)
        worker.start()

    def _on_backup_done(self, ok: bool, msg: str) -> None:
        self._log.append(f"{'✓' if ok else '✗'} {msg}")

    def _save(self) -> None:
        cfg = load_global_config()
        cfg.setdefault("system_modules", {})["backup"] = {
            "enabled":   self._enabled.isChecked(),
            "backend":   self._backend.text().strip(),
            "repo_path": self._repo.text().strip(),
            "password":  self._password.text().strip(),
            "paths":     self._paths.text().strip(),
            "schedule":  self._schedule.currentData(),
        }
        save_global_config(cfg)
        self._status.setText("✓ Saved")


# ── Calendar tab ──────────────────────────────────────────────────────────────

class _CalendarTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        sys_cfg = load_global_config().get("system_modules", {})
        cal_cfg = sys_cfg.get("calendar", {})

        hint = QLabel("Global calendar shared by all Integrated-mode calendar modules.")
        hint.setObjectName("dim")
        layout.addWidget(hint)

        group = QGroupBox("Calendar Configuration")
        form  = QFormLayout(group)

        self._data_path = QLineEdit()
        self._data_path.setPlaceholderText("blank = <nexus>/config/calendar/")
        self._data_path.setText(cal_cfg.get("data_path", ""))
        form.addRow("Data directory:", self._data_path)

        self._caldav_enabled = QCheckBox("Enable CalDAV sync")
        self._caldav_enabled.setChecked(cal_cfg.get("caldav_enabled", False))
        form.addRow("", self._caldav_enabled)

        self._caldav_url = QLineEdit()
        self._caldav_url.setPlaceholderText("http://localhost:5232/")
        self._caldav_url.setText(cal_cfg.get("caldav_url", "http://localhost:5232/"))
        form.addRow("CalDAV URL:", self._caldav_url)

        self._caldav_user = QLineEdit()
        self._caldav_user.setPlaceholderText("username")
        self._caldav_user.setText(cal_cfg.get("caldav_user", ""))
        form.addRow("Username:", self._caldav_user)

        self._caldav_password = QLineEdit()
        self._caldav_password.setEchoMode(QLineEdit.Password)
        self._caldav_password.setPlaceholderText("password")
        self._caldav_password.setText(cal_cfg.get("caldav_password", ""))
        form.addRow("Password:", self._caldav_password)

        layout.addWidget(group)
        layout.addStretch()

        btn_row = QHBoxLayout()
        sync_btn = QPushButton("Sync Now")
        sync_btn.clicked.connect(lambda: QMessageBox.information(
            self, "Sync", "CalDAV sync not yet implemented."))
        btn_row.addWidget(sync_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        save_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._save)
        self._status = QLabel("")
        self._status.setObjectName("dim")
        save_row.addStretch()
        save_row.addWidget(self._status)
        save_row.addWidget(save_btn)
        layout.addLayout(save_row)

    def _save(self) -> None:
        cfg = load_global_config()
        cfg.setdefault("system_modules", {})["calendar"] = {
            "data_path":       self._data_path.text().strip(),
            "caldav_enabled":  self._caldav_enabled.isChecked(),
            "caldav_url":      self._caldav_url.text().strip(),
            "caldav_user":     self._caldav_user.text().strip(),
            "caldav_password": self._caldav_password.text().strip(),
        }
        save_global_config(cfg)
        self._status.setText("✓ Saved")


# ── SDForge tab ───────────────────────────────────────────────────────────────

class _SDForgeTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        sys_cfg    = load_global_config().get("system_modules", {})
        sdforge_cfg = sys_cfg.get("sdforge", {})

        hint = QLabel("Global SDForge instance for Integrated-mode projects.")
        hint.setObjectName("dim")
        layout.addWidget(hint)

        group = QGroupBox("SDForge Configuration")
        form  = QFormLayout(group)

        self._endpoint = QLineEdit()
        self._endpoint.setPlaceholderText("http://127.0.0.1:7860")
        self._endpoint.setText(sdforge_cfg.get("endpoint", "http://127.0.0.1:7860"))
        form.addRow("Endpoint URL:", self._endpoint)

        self._api_key = QLineEdit()
        self._api_key.setEchoMode(QLineEdit.Password)
        self._api_key.setPlaceholderText("optional")
        self._api_key.setText(sdforge_cfg.get("api_key", ""))
        form.addRow("API Key:", self._api_key)

        layout.addWidget(group)
        layout.addStretch()

        save_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._save)
        self._status = QLabel("")
        self._status.setObjectName("dim")
        save_row.addStretch()
        save_row.addWidget(self._status)
        save_row.addWidget(save_btn)
        layout.addLayout(save_row)

    def _save(self) -> None:
        cfg = load_global_config()
        cfg.setdefault("system_modules", {})["sdforge"] = {
            "endpoint": self._endpoint.text().strip(),
            "api_key":  self._api_key.text().strip(),
        }
        save_global_config(cfg)
        self._status.setText("✓ Saved")


# ── Security tab (stub) ───────────────────────────────────────────────────────

class _SecurityTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        lbl = QLabel(
            "Security tools are configured per-project.\n\n"
            "Add the Security system module to a project from the project hub\n"
            "to manage firewall, VPN, and auditing settings for that project."
        )
        lbl.setObjectName("dim")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        layout.addStretch()


# ── Server tab ────────────────────────────────────────────────────────────────

class _ServerTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        sys_cfg    = load_global_config().get("system_modules", {})
        server_cfg = sys_cfg.get("server", {})

        hint = QLabel("Global web server for Integrated-mode projects.")
        hint.setObjectName("dim")
        layout.addWidget(hint)

        group = QGroupBox("Web Server Configuration")
        form  = QFormLayout(group)

        self._web_root = QLineEdit()
        self._web_root.setPlaceholderText("/var/www/html")
        self._web_root.setText(server_cfg.get("web_root", ""))
        form.addRow("Web root path:", self._web_root)

        self._http_port = QLineEdit()
        self._http_port.setPlaceholderText("80")
        self._http_port.setText(str(server_cfg.get("http_port", 80)))
        form.addRow("HTTP port:", self._http_port)

        self._https_port = QLineEdit()
        self._https_port.setPlaceholderText("443")
        self._https_port.setText(str(server_cfg.get("https_port", 443)))
        form.addRow("HTTPS port:", self._https_port)

        layout.addWidget(group)
        layout.addStretch()

        save_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._save)
        self._status = QLabel("")
        self._status.setObjectName("dim")
        save_row.addStretch()
        save_row.addWidget(self._status)
        save_row.addWidget(save_btn)
        layout.addLayout(save_row)

    def _save(self) -> None:
        cfg = load_global_config()
        try:
            http_port  = int(self._http_port.text().strip() or "80")
            https_port = int(self._https_port.text().strip() or "443")
        except ValueError:
            QMessageBox.warning(self, "Invalid", "Ports must be integers.")
            return
        cfg.setdefault("system_modules", {})["server"] = {
            "web_root":   self._web_root.text().strip(),
            "http_port":  http_port,
            "https_port": https_port,
        }
        save_global_config(cfg)
        self._status.setText("✓ Saved")


# ── Main dialog ───────────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(900, 640)

        layout = QVBoxLayout(self)

        self._tabs = QTabWidget()

        self._gen_tab      = _GeneralTab()
        self._app_tab      = _AppearanceTab()
        self._setup_tab    = _SetupTab()
        self._git_tab      = _GitTab()
        self._backup_tab   = _BackupTab()
        self._calendar_tab = _CalendarTab()
        self._ai_tab       = _AITab()
        self._mcp_tab      = _MCPTab()
        self._sdforge_tab  = _SDForgeTab()
        self._security_tab = _SecurityTab()
        self._server_tab   = _ServerTab()

        self._tabs.addTab(self._gen_tab,      "General")
        self._tabs.addTab(self._app_tab,      "Appearance")
        self._tabs.addTab(self._setup_tab,    "Setup")
        self._tabs.addTab(self._git_tab,      "Git")
        self._tabs.addTab(self._backup_tab,   "Backup")
        self._tabs.addTab(self._calendar_tab, "Calendar")
        self._tabs.addTab(self._ai_tab,       "AI Config")
        self._tabs.addTab(self._mcp_tab,      "MCP Servers")
        self._tabs.addTab(self._sdforge_tab,  "SDForge")
        self._tabs.addTab(self._security_tab, "Security")
        self._tabs.addTab(self._server_tab,   "Server")

        self._app_tab.theme_changed.connect(self._apply_theme)

        layout.addWidget(self._tabs)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _apply_theme(self, name: str) -> None:
        from nexus.ui.gui.theme import get_gui_theme
        if self.parent() and hasattr(self.parent(), "apply_theme"):
            self.parent().apply_theme(name)
        self.setStyleSheet(get_gui_theme(name))
