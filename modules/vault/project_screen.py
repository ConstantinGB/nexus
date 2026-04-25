from __future__ import annotations
import shutil
from pathlib import Path

from textual.widgets import Label, Button, Log
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.core.platform import open_path
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
        {"id": "vault_dir",       "label": "Vault / container directory",
         "placeholder": "~/vault"},
        {"id": "age_key_path",    "label": "age key path (optional)",
         "placeholder": "~/.age/key.txt", "optional": True},
        {"id": "keepassxc_db",    "label": "KeePassXC database path (optional)",
         "placeholder": "~/vault/passwords.kdbx", "optional": True},
        {"id": "veracrypt_volume","label": "VeraCrypt volume path (optional)",
         "placeholder": "~/vault/encrypted.vc", "optional": True},
    ]

    DEFAULT_CSS = _screen_css("VaultProjectScreen") + """
    .tool-row  { height: 1; }
    .tool-name { color: #E0E0FF; width: 18; }
    .tool-desc { color: #8080AA; width: 1fr; }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._tools: dict[str, bool] = {}
        self._age_key_path = Path.home() / ".age" / "key.txt"  # overridden in _populate_content

    # ── Action buttons ────────────────────────────────────────────────────────

    def _compose_action_buttons(self) -> list:
        return [
            Button("GPG: List Keys",   id="btn-gpg-list",    variant="primary"),
            Button("GPG: Gen Key",     id="btn-gpg-gen"),
            Button("GPG: Export Key",  id="btn-gpg-export"),
            Button("GPG: Import Key",  id="btn-gpg-import"),
            Button("age: New Key",     id="btn-age-new"),
            Button("Encrypt File",     id="btn-encrypt-file"),
            Button("Decrypt File",     id="btn-decrypt-file"),
            Button("KeePassXC: List",  id="btn-kp-list"),
            Button("VeraCrypt: Mount", id="btn-vc-mount"),
            Button("VeraCrypt: Dismount", id="btn-vc-dismount"),
            Button("Open Vault Dir",   id="btn-open-vault"),
        ]

    # ── Main content ──────────────────────────────────────────────────────────

    async def _populate_content(self) -> None:
        area = self.query_one("#content-area", Vertical)
        await area.remove_children()

        vault_dir = Path(self._mod.get("vault_dir", "")).expanduser()
        age_key_raw = self._mod.get("age_key_path", "").strip()
        self._age_key_path = (
            Path(age_key_raw).expanduser() if age_key_raw
            else Path.home() / ".age" / "key.txt"
        )
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
            ui_log = self.query_one("#output-log")
            ui_log.write_line(
                "GPG key generation requires an interactive terminal.\n"
                "Run this in a separate terminal:\n\n"
                "  gpg --full-generate-key\n\n"
                "Then verify with: gpg --list-keys"
            )
            self.app.notify("GPG keygen command logged.", severity="information")

        elif bid == "btn-gpg-export":
            self.app.push_screen(
                InputModal("Export GPG Key", "Key ID or email to export:", "user@example.com"),
                self._gpg_export,
            )

        elif bid == "btn-gpg-import":
            self.app.push_screen(
                InputModal("Import GPG Key", "Path to armored key file:", "~/pubkey.asc"),
                self._gpg_import,
            )

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

        elif bid == "btn-decrypt-file":
            if not self._age_key_path.exists():
                self.app.notify("No age key found at ~/.age/key.txt. Generate one first.", severity="warning")
                return
            self.app.push_screen(
                InputModal("Decrypt File", "File path to decrypt (.age):", "~/file.txt.age"),
                lambda path: self._decrypt_with_age(path),
            )

        elif bid == "btn-kp-list":
            db = self._mod.get("keepassxc_db", "").strip()
            if not db:
                self.app.notify("No KeePassXC database configured in setup.", severity="warning")
                return
            if not self._tools.get("keepassxc-cli"):
                self.app.notify("keepassxc-cli not found on PATH.", severity="warning")
                return
            self.app.push_screen(
                InputModal("KeePassXC Password", "Master password:", ""),
                lambda pw: self.run_worker(self._kp_list(db, pw)) if pw else None,
            )

        elif bid == "btn-vc-mount":
            vol = self._mod.get("veracrypt_volume", "").strip()
            if not vol:
                self.app.notify("No VeraCrypt volume configured in setup.", severity="warning")
                return
            self.app.push_screen(
                InputModal("Mount VeraCrypt", "Mount point directory:", "/mnt/vault"),
                lambda mp: self.run_worker(
                    self._run_cmd(["veracrypt", "--non-interactive", vol, mp])
                ) if mp else None,
            )

        elif bid == "btn-vc-dismount":
            vol = self._mod.get("veracrypt_volume", "").strip()
            self.run_worker(
                self._run_cmd(
                    ["veracrypt", "--non-interactive", "--dismount"] +
                    ([vol] if vol else [])
                )
            )

        elif bid == "btn-open-vault":
            vault_dir.mkdir(parents=True, exist_ok=True)
            self.run_worker(self._run_cmd(open_path(vault_dir)))

    def _pubkey_from_age_key(self) -> str:
        """Return public key via age-keygen -y, falling back to comment parsing."""
        import subprocess
        try:
            r = subprocess.run(
                ["age-keygen", "-y", str(self._age_key_path)],
                capture_output=True, text=True,
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except FileNotFoundError:
            pass
        for line in self._age_key_path.read_text(errors="replace").splitlines():
            if line.startswith("# public key:"):
                return line.split(":", 1)[1].strip()
        return ""

    def _encrypt_with_age(self, file_path_str: str | None) -> None:
        if not file_path_str:
            return
        file_path = Path(file_path_str).expanduser()
        if not file_path.exists():
            self.app.notify(f"File not found: {file_path}", severity="error")
            return
        output_path = file_path.with_suffix(file_path.suffix + ".age")
        try:
            pubkey = self._pubkey_from_age_key()
            if not pubkey:
                self.app.notify("Could not read public key from ~/.age/key.txt", severity="error")
                return
            self.run_worker(
                self._run_cmd(["age", "-r", pubkey, "-o", str(output_path), str(file_path)])
            )
        except Exception:
            log.exception("Failed to read age key")
            self.app.notify("Could not read age key.", severity="error")

    def _gpg_export(self, key_id: str | None) -> None:
        if not key_id:
            return
        vault_dir = Path(self._mod.get("vault_dir", "")).expanduser()
        out_file  = vault_dir / f"{key_id.replace('@', '_').replace(' ', '_')}.asc"
        self.run_worker(
            self._run_cmd(["gpg", "--export", "--armor", "--output", str(out_file), key_id])
        )

    def _gpg_import(self, file_path_str: str | None) -> None:
        if not file_path_str:
            return
        file_path = Path(file_path_str).expanduser()
        if not file_path.exists():
            self.app.notify(f"File not found: {file_path}", severity="error")
            return
        self.run_worker(self._run_cmd(["gpg", "--import", str(file_path)]))

    async def _kp_list(self, db: str, password: str) -> None:
        import asyncio as _aio
        from textual.widgets import Log as _Log
        ui_log = self.query_one("#output-log", _Log)
        ui_log.write_line(f"$ keepassxc-cli ls {db}")
        try:
            proc = await _aio.create_subprocess_exec(
                "keepassxc-cli", "ls", "--no-password", db,
                stdin=_aio.subprocess.PIPE,
                stdout=_aio.subprocess.PIPE,
                stderr=_aio.subprocess.STDOUT,
            )
            out, _ = await proc.communicate(input=(password + "\n").encode())
            for line in out.decode(errors="replace").splitlines():
                ui_log.write_line(line)
            ui_log.write_line("✓ Done" if proc.returncode == 0 else f"✗ Exited {proc.returncode}")
        except FileNotFoundError:
            ui_log.write_line("✗ keepassxc-cli not found on PATH.")
        except Exception as exc:
            log.exception("keepassxc-cli list failed")
            ui_log.write_line(f"✗ {exc}")

    def _decrypt_with_age(self, file_path_str: str | None) -> None:
        if not file_path_str:
            return
        file_path = Path(file_path_str).expanduser()
        if not file_path.exists():
            self.app.notify(f"File not found: {file_path}", severity="error")
            return
        if file_path.suffix == ".age":
            output_path = file_path.with_suffix("")
        else:
            output_path = file_path.with_suffix(file_path.suffix + ".decrypted")
        self.run_worker(
            self._run_cmd([
                "age", "--decrypt",
                "-i", str(self._age_key_path),
                "-o", str(output_path),
                str(file_path),
            ])
        )
