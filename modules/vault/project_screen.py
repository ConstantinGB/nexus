from __future__ import annotations
import shutil
from pathlib import Path

from textual.widgets import Label, Button, Log
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.ui.base_project_screen import BaseProjectScreen, InputModal, _screen_css

log = get("vault.project_screen")

_TOOLS = [
    ("gpg",          "GPG (asymmetric encryption, signing)"),
    ("age",          "age (modern file encryption)"),
    ("veracrypt",    "VeraCrypt (encrypted containers)"),
    ("keepassxc-cli","KeePassXC CLI (password manager)"),
    ("ssh-keygen",   "ssh-keygen (SSH key generation)"),
    ("cryptsetup",   "cryptsetup (LUKS disk encryption)"),
]


class VaultProjectScreen(BaseProjectScreen):
    MODULE_KEY   = "vault"
    MODULE_LABEL = "VAULT"
    SETUP_FIELDS = [
        {"id": "vault_dir", "label": "Vault / container directory",
         "placeholder": "~/vault"},
    ]

    DEFAULT_CSS = _screen_css("VaultProjectScreen") + """
    .tool-row  { height: 1; }
    .tool-name { color: #E0E0FF; width: 18; }
    .tool-desc { color: #8080AA; width: 1fr; }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._tools: dict[str, bool] = {}
        self._age_key_path = Path.home() / ".age" / "key.txt"

    # ── Action buttons ────────────────────────────────────────────────────────

    def _compose_action_buttons(self) -> list:
        return [
            Button("GPG: List Keys",  id="btn-gpg-list",    variant="primary"),
            Button("GPG: Gen Key",    id="btn-gpg-gen"),
            Button("age: New Key",    id="btn-age-new"),
            Button("Encrypt File",    id="btn-encrypt-file"),
            Button("Open Vault Dir",  id="btn-open-vault"),
        ]

    # ── Main content ──────────────────────────────────────────────────────────

    async def _populate_content(self) -> None:
        area = self.query_one("#content-area", Vertical)
        await area.remove_children()

        vault_dir = Path(self._mod.get("vault_dir", "")).expanduser()
        self._tools = {binary: shutil.which(binary) is not None for binary, _ in _TOOLS}

        widgets: list = [
            Horizontal(
                Label("Vault dir:", classes="info-key"),
                Label(str(vault_dir), classes="info-val"),
                classes="info-row",
            ),
            Label("Installed tools:", classes="section-label"),
        ]

        for binary, description in _TOOLS:
            found = self._tools[binary]
            widgets.append(
                Horizontal(
                    Label(f"  {'✓' if found else '✗'} {binary}", classes="tool-name"),
                    Label(description, classes="tool-desc"),
                    classes="tool-row " + ("status-ok" if found else "status-err"),
                )
            )

        widgets.append(Label("Key status:", classes="section-label"))
        age_key_exists = self._age_key_path.exists()
        widgets.append(
            Horizontal(
                Label("  age key:", classes="info-key"),
                Label(
                    str(self._age_key_path) if age_key_exists else "not found (~/.age/key.txt)",
                    classes="info-val " + ("status-ok" if age_key_exists else "hint"),
                ),
                classes="info-row",
            )
        )

        await area.mount(*widgets)

    # ── Button handler ────────────────────────────────────────────────────────

    def _handle_action(self, bid: str | None) -> None:
        vault_dir = Path(self._mod.get("vault_dir", "")).expanduser()

        if bid == "btn-gpg-list":
            self.run_worker(self._run_cmd(["gpg", "--list-keys"]))

        elif bid == "btn-gpg-gen":
            # gpg --full-generate-key is interactive; log the command instead
            ui_log = self.query_one("#output-log")
            ui_log.write_line(
                "GPG key generation requires an interactive terminal.\n"
                "Run this in a separate terminal:\n\n"
                "  gpg --full-generate-key\n\n"
                "Then verify with: gpg --list-keys"
            )
            self.app.notify("GPG keygen command logged.", severity="information")

        elif bid == "btn-age-new":
            key_path = str(self._age_key_path)
            age_dir  = self._age_key_path.parent
            try:
                age_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            if self._age_key_path.exists():
                self.app.notify(
                    f"age key already exists at {key_path}. Delete it first to regenerate.",
                    severity="warning",
                )
            else:
                self.run_worker(self._run_cmd(["age-keygen", "-o", key_path]))

        elif bid == "btn-encrypt-file":
            if not self._age_key_path.exists():
                self.app.notify("No age key found at ~/.age/key.txt. Generate one first.", severity="warning")
                return
            self.app.push_screen(
                InputModal("Encrypt File", "File path to encrypt:", "~/sensitive-file.txt"),
                lambda path: self._encrypt_with_age(path),
            )

        elif bid == "btn-open-vault":
            vault_dir.mkdir(parents=True, exist_ok=True)
            self.run_worker(self._run_cmd(["xdg-open", str(vault_dir)]))

    def _encrypt_with_age(self, file_path_str: str | None) -> None:
        if not file_path_str:
            return
        file_path = Path(file_path_str).expanduser()
        if not file_path.exists():
            self.app.notify(f"File not found: {file_path}", severity="error")
            return
        output_path = file_path.with_suffix(file_path.suffix + ".age")
        try:
            key_text = self._age_key_path.read_text()
            pubkey = ""
            for line in key_text.splitlines():
                if line.startswith("# public key:"):
                    pubkey = line.split(":", 1)[1].strip()
                    break
            if not pubkey:
                self.app.notify("Could not read public key from ~/.age/key.txt", severity="error")
                return
            self.run_worker(
                self._run_cmd(["age", "-r", pubkey, "-o", str(output_path), str(file_path)])
            )
        except Exception:
            log.exception("Failed to read age key")
            self.app.notify("Could not read age key.", severity="error")
