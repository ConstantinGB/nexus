"""Settings dialog for the Nexus GUI — mirrors the TUI SettingsScreen tabs."""
from __future__ import annotations
import shutil
import subprocess
import sys
from pathlib import Path

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTabWidget, QWidget, QLabel, QPushButton, QLineEdit, QComboBox,
    QGroupBox, QScrollArea, QFrame, QTextEdit, QListWidget, QListWidgetItem,
    QSizePolicy, QMessageBox, QInputDialog, QSplitter, QTableWidget,
    QTableWidgetItem, QHeaderView,
)

_SETTINGS_ROOT = Path(__file__).parent.parent.parent.parent

from nexus.core.config_manager import load_global_config, save_global_config
from nexus.core.logger import get
from nexus.ui.gui.theme import GUI_THEMES, GUI_THEME_LABELS, DEFAULT_GUI_THEME

log = get("ui.gui.settings_dialog")


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
                self.result.emit(True, "API key verified.")
            else:
                self.result.emit(False, f"HTTP {r.status_code}: {r.text[:120]}")
        except Exception as exc:
            self.result.emit(False, str(exc))


class _TestLocalWorker(QThread):
    result = Signal(bool, str)

    def __init__(self, endpoint: str, model: str) -> None:
        super().__init__()
        self._endpoint = endpoint.rstrip("/")
        self._model    = model

    def run(self) -> None:
        try:
            import httpx
            r = httpx.post(
                f"{self._endpoint}/chat/completions",
                json={"model": self._model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5},
                timeout=15,
            )
            if r.status_code < 400:
                self.result.emit(True, f"Connected ({r.status_code}).")
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
        try:
            proc = subprocess.Popen(
                self._cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True,
            )
            if proc.stdout:
                for line in proc.stdout:
                    self.line_ready.emit(line.rstrip())
            proc.wait()
            self.done.emit(proc.returncode or 0)
        except Exception as exc:
            self.line_ready.emit(f"Error: {exc}")
            self.done.emit(1)


# ── Dependency list (mirrors TUI _MODULE_DEPS) ───────────────────────────────

_DEPS: list[tuple[str, str, str | None, str | None]] = [
    # (module_group, display_name, apt_pkg_or_None, special_cmd_or_None)
    ("System",    "xclip (X11 clipboard)",     "xclip",              None),
    ("System",    "wl-clipboard (Wayland)",     "wl-clipboard",       None),
    ("Git",       "Git",                        "git",                None),
    ("Web",       "Node.js",                    "nodejs",             None),
    ("Web",       "npm",                        "npm",                None),
    ("Research",  "ripgrep (rg)",               "ripgrep",            None),
    ("Codex",     "ripgrep (rg)",               "ripgrep",            None),
    ("Journal",   "pdflatex",                   "texlive-latex-base", None),
    ("Streaming", "OBS Studio",                 "obs-studio",         None),
    ("Emulator",  "RetroArch",                  "retroarch",          None),
    ("Vault",     "GnuPG",                      "gnupg",              None),
    ("Vault",     "age",                        "age",                None),
    ("Vault",     "KeePassXC",                  "keepassxc",          None),
    ("Vault",     "cryptsetup",                 "cryptsetup",         None),
    ("Server",    "Docker",                     "docker.io",          None),
    ("Backup",    "restic",                     "restic",             None),
    ("LocalAI",   "Ollama",                     None, "curl -fsSL https://ollama.com/install.sh | sh"),
    ("Security",  "ufw",                        "ufw",                None),
    ("Security",  "nmap",                       "nmap",               None),
    ("Security",  "fail2ban",                   "fail2ban",           None),
    ("YouTube",   "ffmpeg",                     "ffmpeg",             None),
]

_DEP_BINARY: dict[str, str] = {
    "xclip (X11 clipboard)":  "xclip",
    "wl-clipboard (Wayland)": "wl-paste",
    "Git":                    "git",
    "Node.js":                "node",
    "npm":                    "npm",
    "ripgrep (rg)":           "rg",
    "pdflatex":               "pdflatex",
    "OBS Studio":             "obs",
    "RetroArch":              "retroarch",
    "GnuPG":                  "gpg",
    "age":                    "age",
    "KeePassXC":              "keepassxc-cli",
    "cryptsetup":             "cryptsetup",
    "Docker":                 "docker",
    "restic":                 "restic",
    "Ollama":                 "ollama",
    "ufw":                    "ufw",
    "nmap":                   "nmap",
    "fail2ban":               "fail2ban-client",
    "ffmpeg":                 "ffmpeg",
}


# ── AI tab ────────────────────────────────────────────────────────────────────

class _AITab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cfg     = load_global_config()
        self._worker: QThread | None = None
        self._advanced = False
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        ai_cfg   = self._cfg.get("ai", {})
        provider = ai_cfg.get("provider", "api_key")

        # ── Provider + Basic/Advanced row ─────────────────────────────────────
        top_row = QHBoxLayout()

        prov_box = QGroupBox("AI Provider")
        prov_lay = QHBoxLayout(prov_box)
        self._btn_apikey = QPushButton("API Key")
        self._btn_local  = QPushButton("Local Model")
        for btn in (self._btn_apikey, self._btn_local):
            btn.setCheckable(True)
            prov_lay.addWidget(btn)
        prov_lay.addStretch()
        self._btn_apikey.clicked.connect(lambda: self._set_provider("api_key"))
        self._btn_local.clicked.connect(lambda: self._set_provider("local"))
        top_row.addWidget(prov_box, 1)

        # Advanced toggle — visually distinct: purple bg, dark text
        self._adv_btn = QPushButton("Advanced ▾")
        self._adv_btn.setCheckable(True)
        self._adv_btn.setFixedHeight(36)
        self._adv_btn.setStyleSheet(
            "QPushButton { background: #B45AFF; color: #1A0A2E; font-weight: bold;"
            " border-radius: 4px; padding: 4px 12px; }"
            "QPushButton:checked { background: #8A2BE2; color: #E0D0FF; }"
            "QPushButton:hover { background: #C870FF; }"
        )
        self._adv_btn.clicked.connect(self._toggle_advanced)
        top_row.addWidget(self._adv_btn)

        layout.addLayout(top_row)

        # ── API key section ───────────────────────────────────────────────────
        self._api_group = QGroupBox("Anthropic API Key")
        api_lay = QFormLayout(self._api_group)
        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.Password)
        self._api_key_input.setText(ai_cfg.get("api_key", ""))
        self._api_key_input.setPlaceholderText("sk-ant-...")
        api_lay.addRow("API Key:", self._api_key_input)
        verify_row = QHBoxLayout()
        self._verify_btn    = QPushButton("Verify")
        self._verify_status = QLabel("—")
        self._verify_status.setObjectName("dim")
        self._verify_btn.clicked.connect(self._verify)
        verify_row.addWidget(self._verify_btn)
        verify_row.addWidget(self._verify_status)
        verify_row.addStretch()
        api_lay.addRow("", verify_row)
        layout.addWidget(self._api_group)

        # ── Local section ─────────────────────────────────────────────────────
        self._local_group = QGroupBox("Local Model (OpenAI-compatible)")
        local_lay = QFormLayout(self._local_group)
        self._local_endpoint = QLineEdit()
        self._local_endpoint.setPlaceholderText("http://localhost:11434")
        self._local_endpoint.setText(ai_cfg.get("local_endpoint", ""))
        local_lay.addRow("Endpoint:", self._local_endpoint)
        self._local_model = QLineEdit()
        self._local_model.setPlaceholderText("llama3.2")
        self._local_model.setText(ai_cfg.get("local_model", ""))
        local_lay.addRow("Model:", self._local_model)
        test_row = QHBoxLayout()
        self._test_btn    = QPushButton("Test Connection")
        self._test_status = QLabel("—")
        self._test_status.setObjectName("dim")
        self._test_btn.clicked.connect(self._test_local)
        test_row.addWidget(self._test_btn)
        test_row.addWidget(self._test_status)
        test_row.addStretch()
        local_lay.addRow("", test_row)
        layout.addWidget(self._local_group)

        # ── Advanced section ──────────────────────────────────────────────────
        self._adv_group = QGroupBox("Advanced Options")
        adv_lay = QFormLayout(self._adv_group)

        self._adv_model = QLineEdit()
        self._adv_model.setPlaceholderText("claude-sonnet-4-6")
        self._adv_model.setText(ai_cfg.get("model", ""))
        adv_lay.addRow("Model override:", self._adv_model)

        self._adv_max_tokens = QLineEdit()
        self._adv_max_tokens.setPlaceholderText("8096")
        val = ai_cfg.get("max_tokens", "")
        self._adv_max_tokens.setText(str(val) if val else "")
        adv_lay.addRow("Max tokens:", self._adv_max_tokens)

        self._adv_temperature = QLineEdit()
        self._adv_temperature.setPlaceholderText("1.0")
        temp = ai_cfg.get("temperature", "")
        self._adv_temperature.setText(str(temp) if temp else "")
        adv_lay.addRow("Temperature:", self._adv_temperature)

        self._adv_context = QLineEdit()
        self._adv_context.setPlaceholderText("4096  (local models only)")
        ctx = ai_cfg.get("context_window", "")
        self._adv_context.setText(str(ctx) if ctx else "")
        adv_lay.addRow("Context window:", self._adv_context)

        self._adv_group.setVisible(False)
        layout.addWidget(self._adv_group)

        layout.addStretch()

        # ── Save ──────────────────────────────────────────────────────────────
        save_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._save)
        save_row.addStretch()
        save_row.addWidget(save_btn)
        layout.addLayout(save_row)

        self._set_provider(provider)

    # ── Visibility ────────────────────────────────────────────────────────────

    def _toggle_advanced(self) -> None:
        self._advanced = self._adv_btn.isChecked()
        self._adv_btn.setText("Advanced ▴" if self._advanced else "Advanced ▾")
        self._adv_group.setVisible(self._advanced)

    def _set_provider(self, provider: str) -> None:
        self._provider = provider
        self._btn_apikey.setChecked(provider == "api_key")
        self._btn_local.setChecked(provider == "local")
        self._api_group.setVisible(provider == "api_key")
        self._local_group.setVisible(provider == "local")

    # ── Workers ───────────────────────────────────────────────────────────────

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

    def _test_local(self) -> None:
        ep = self._local_endpoint.text().strip()
        m  = self._local_model.text().strip()
        if not ep or not m:
            self._test_status.setText("Fill endpoint and model first.")
            return
        self._test_btn.setEnabled(False)
        self._test_status.setText("Testing…")
        self._worker = _TestLocalWorker(ep, m)
        self._worker.result.connect(self._on_test)
        self._worker.start()

    def _on_test(self, ok: bool, msg: str) -> None:
        self._test_status.setText(f"{'✓' if ok else '✗'} {msg}")
        self._test_btn.setEnabled(True)
        self._worker = None

    # ── Save ──────────────────────────────────────────────────────────────────

    def _save(self) -> None:
        cfg = load_global_config()
        ai  = cfg.setdefault("ai", {})
        ai["provider"] = self._provider
        if self._provider == "api_key":
            ai["api_key"] = self._api_key_input.text().strip()
        else:
            ai["local_endpoint"] = self._local_endpoint.text().strip()
            ai["local_model"]    = self._local_model.text().strip()
        # Advanced fields (only save non-empty)
        model = self._adv_model.text().strip()
        if model:
            ai["model"] = model
        else:
            ai.pop("model", None)
        max_tok = self._adv_max_tokens.text().strip()
        if max_tok.isdigit():
            ai["max_tokens"] = int(max_tok)
        else:
            ai.pop("max_tokens", None)
        temp_str = self._adv_temperature.text().strip()
        try:
            ai["temperature"] = float(temp_str)
        except ValueError:
            ai.pop("temperature", None)
        ctx_str = self._adv_context.text().strip()
        if ctx_str.isdigit():
            ai["context_window"] = int(ctx_str)
        else:
            ai.pop("context_window", None)
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

        cfg   = load_global_config()
        current = cfg.get("ui", {}).get("gui_theme", DEFAULT_GUI_THEME)

        group = QGroupBox("GUI Colour Theme")
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
        # Extract bg and accent colors from the theme for the swatch
        from nexus.ui.gui.theme import GUI_THEMES
        qss = GUI_THEMES.get(name, "")
        # Quick color extraction: find background-color in first line
        bg = "#1A0A2E"
        for line in qss.splitlines():
            if "background-color:" in line and bg == "#1A0A2E":
                parts = line.split("background-color:")
                if len(parts) > 1:
                    bg = parts[1].strip().rstrip(";").strip()
                    break
        self._swatch.setStyleSheet(f"background: {bg}; border-radius: 4px;")

    def _save(self) -> None:
        name = self._combo.currentData()
        cfg = load_global_config()
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

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_lay = QVBoxLayout(content)
        content_lay.setSpacing(4)

        last_group = ""
        for group, name, apt_pkg, special in _DEPS:
            if group != last_group:
                lbl = QLabel(f"── {group} ──")
                lbl.setObjectName("subtitle")
                content_lay.addWidget(lbl)
                last_group = group
            binary = _DEP_BINARY.get(name, name.split()[0].lower())
            installed = shutil.which(binary) is not None
            row = _DepRow(name, installed, apt_pkg, special)
            row.install_requested.connect(self._install)
            content_lay.addWidget(row)

        content_lay.addStretch()
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


# ── MCP tab ───────────────────────────────────────────────────────────────────

class _MCPTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected_sid: str | None = None
        self._build()

    def _build(self) -> None:
        from nexus.ai.mcp_registry import REGISTRY as MCP_REGISTRY

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # Top: horizontal split — active list | catalog
        top_splitter = QSplitter(Qt.Horizontal)

        # ── Left: active servers ──────────────────────────────────────────────
        left = QWidget()
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

        # ── Right: catalog ────────────────────────────────────────────────────
        right = QWidget()
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

        # ── Bottom: detail / edit panel ───────────────────────────────────────
        self._detail_group = QGroupBox("Edit Server Configuration")
        self._detail_group.setVisible(False)
        detail_lay = QVBoxLayout(self._detail_group)
        detail_lay.setSpacing(6)

        detail_form = QFormLayout()
        self._edit_command = QLineEdit()
        self._edit_command.setPlaceholderText("e.g. npx")
        detail_form.addRow("Command:", self._edit_command)

        self._edit_args = QLineEdit()
        self._edit_args.setPlaceholderText("space-separated arguments")
        detail_form.addRow("Args:", self._edit_args)
        detail_lay.addLayout(detail_form)

        env_lbl = QLabel("Environment Variables:")
        env_lbl.setObjectName("subtitle")
        detail_lay.addWidget(env_lbl)

        self._env_table = QTableWidget(0, 2)
        self._env_table.setHorizontalHeaderLabels(["Key", "Value"])
        self._env_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._env_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._env_table.setMaximumHeight(140)
        detail_lay.addWidget(self._env_table)

        env_btn_row = QHBoxLayout()
        add_env_btn = QPushButton("+ Row")
        add_env_btn.clicked.connect(self._add_env_row)
        del_env_btn = QPushButton("− Row")
        del_env_btn.clicked.connect(self._del_env_row)
        env_btn_row.addWidget(add_env_btn)
        env_btn_row.addWidget(del_env_btn)
        env_btn_row.addStretch()
        detail_lay.addLayout(env_btn_row)

        save_row = QHBoxLayout()
        save_edit_btn = QPushButton("Save Changes")
        save_edit_btn.setObjectName("primary")
        save_edit_btn.clicked.connect(self._save_server_edit)
        save_row.addStretch()
        save_row.addWidget(save_edit_btn)
        detail_lay.addLayout(save_row)

        layout.addWidget(self._detail_group)

        self._refresh_active()

    # ── Active list management ─────────────────────────────────────────────────

    def _refresh_active(self) -> None:
        from nexus.core.config_manager import load_global_config
        self._active_list.clear()
        cfg     = load_global_config()
        servers = cfg.get("mcp", {}).get("servers") or {}
        for sid, scfg in servers.items():
            args_preview = " ".join(scfg.get("args", []))[:40]
            item = QListWidgetItem(f"{sid}  —  {scfg.get('command', '')} {args_preview}")
            item.setData(Qt.UserRole, sid)
            self._active_list.addItem(item)
        n = len(servers)
        self._summary_lbl.setText(f"{n} server{'s' if n != 1 else ''} active")
        # Hide detail panel if the previously selected server was removed
        if self._selected_sid and self._selected_sid not in servers:
            self._detail_group.setVisible(False)
            self._selected_sid = None

    def _on_active_selected(self, current: QListWidgetItem | None, _prev) -> None:
        if current is None:
            self._detail_group.setVisible(False)
            self._selected_sid = None
            return
        sid = current.data(Qt.UserRole)
        self._selected_sid = sid
        from nexus.core.config_manager import load_global_config
        cfg    = load_global_config()
        scfg   = (cfg.get("mcp", {}).get("servers") or {}).get(sid, {})
        self._edit_command.setText(scfg.get("command", ""))
        self._edit_args.setText(" ".join(scfg.get("args", [])))
        env = scfg.get("env", {})
        self._env_table.setRowCount(0)
        for k, v in env.items():
            row = self._env_table.rowCount()
            self._env_table.insertRow(row)
            self._env_table.setItem(row, 0, QTableWidgetItem(k))
            self._env_table.setItem(row, 1, QTableWidgetItem(str(v)))
        self._detail_group.setVisible(True)
        self._detail_group.setTitle(f"Edit — {sid}")

    # ── Env table helpers ──────────────────────────────────────────────────────

    def _add_env_row(self) -> None:
        row = self._env_table.rowCount()
        self._env_table.insertRow(row)
        self._env_table.setItem(row, 0, QTableWidgetItem(""))
        self._env_table.setItem(row, 1, QTableWidgetItem(""))

    def _del_env_row(self) -> None:
        row = self._env_table.currentRow()
        if row >= 0:
            self._env_table.removeRow(row)

    # ── Save edit ─────────────────────────────────────────────────────────────

    def _save_server_edit(self) -> None:
        if not self._selected_sid:
            return
        from nexus.core.config_manager import load_global_config, save_global_config
        import shlex
        cfg    = load_global_config()
        scfg   = (cfg.get("mcp", {}).get("servers") or {}).get(self._selected_sid)
        if scfg is None:
            return
        scfg["command"] = self._edit_command.text().strip()
        args_text = self._edit_args.text().strip()
        scfg["args"] = shlex.split(args_text) if args_text else []
        env: dict[str, str] = {}
        for row in range(self._env_table.rowCount()):
            k_item = self._env_table.item(row, 0)
            v_item = self._env_table.item(row, 1)
            k = (k_item.text().strip() if k_item else "")
            v = (v_item.text().strip() if v_item else "")
            if k:
                env[k] = v
        scfg["env"] = env
        save_global_config(cfg)
        self._refresh_active()
        QMessageBox.information(self, "Saved", f"Server '{self._selected_sid}' updated.")

    # ── Add / remove from catalog ─────────────────────────────────────────────

    def _add_server(self, item: QListWidgetItem) -> None:
        from nexus.ai.mcp_registry import MCPServerSpec
        from nexus.core.config_manager import load_global_config, save_global_config
        spec: MCPServerSpec = item.data(Qt.UserRole)
        env_vals: dict[str, str] = {}
        for key in spec.required_env:
            val, ok = QInputDialog.getText(self, f"Configure {spec.name}", f"{key}:")
            if not ok:
                return
            env_vals[key] = val
        cfg = load_global_config()
        server_cfg = spec.default_config()
        server_cfg["env"].update(env_vals)
        cfg.setdefault("mcp", {}).setdefault("servers", {})[spec.id] = server_cfg
        save_global_config(cfg)
        self._refresh_active()

    def _remove_server(self) -> None:
        from nexus.core.config_manager import load_global_config, save_global_config
        item = self._active_list.currentItem()
        if not item:
            return
        sid = item.data(Qt.UserRole)
        cfg = load_global_config()
        (cfg.get("mcp", {}).get("servers") or {}).pop(sid, None)
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

        cfg     = load_global_config()
        ai_cfg  = cfg.get("ai", {})

        group = QGroupBox("Defaults")
        form  = QFormLayout(group)

        self._panel_combo = QComboBox()
        for label, val in [("Claude", "chat"), ("Local AI", "local"), ("Shell", "shell")]:
            self._panel_combo.addItem(label, userData=val)
            if val == ai_cfg.get("default_panel", "chat"):
                self._panel_combo.setCurrentIndex(self._panel_combo.count() - 1)
        form.addRow("Default chat panel:", self._panel_combo)
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


# ── Main dialog ───────────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(760, 560)

        layout = QVBoxLayout(self)

        self._tabs = QTabWidget()
        self._ai_tab   = _AITab()
        self._app_tab  = _AppearanceTab()
        self._setup_tab = _SetupTab()
        self._mcp_tab  = _MCPTab()
        self._gen_tab  = _GeneralTab()

        self._tabs.addTab(self._ai_tab,    "AI Config")
        self._tabs.addTab(self._app_tab,   "Appearance")
        self._tabs.addTab(self._setup_tab, "Setup")
        self._tabs.addTab(self._mcp_tab,   "MCP Servers")
        self._tabs.addTab(self._gen_tab,   "General")

        # Wire appearance → live theme update on parent window
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
        # Update parent (NexusGuiApp) theme
        if self.parent() and hasattr(self.parent(), "apply_theme"):
            self.parent().apply_theme(name)
        # Also update this dialog
        self.setStyleSheet(get_gui_theme(name))
