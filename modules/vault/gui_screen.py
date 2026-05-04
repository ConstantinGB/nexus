from __future__ import annotations

import shutil
from nexus.core.project_manager import ProjectInfo
from nexus.ui.gui.module_base import ModuleGuiBase

log = __import__("nexus.core.logger", fromlist=["get"]).get("vault.gui_screen")

_TOOLS = [("gpg", "GPG"), ("age", "age"), ("veracrypt", "VeraCrypt"),
          ("keepassxc-cli", "KeePassXC")]


class GuiScreen(ModuleGuiBase):
    SKILL_SCOPES = ["global", "vault"]

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"Vault — {project.name}")
        self._mod = self._cfg.get("vault", {})
        self._populate()

    def _build_toolbar(self) -> None:
        self._add_btn("GPG: List Keys",    self._gpg_list,    primary=True)
        self._add_btn("GPG: Gen Key",      self._gpg_gen)
        self._add_btn("age: New Key",      self._age_new_key)
        self._add_btn("Encrypt File",      self._encrypt)
        self._add_btn("Decrypt File",      self._decrypt)
        self._add_btn("KeePassXC: List",   self._kp_list)
        self._add_btn("VeraCrypt: Mount",  self._vc_mount)
        self._add_btn("VeraCrypt: Dismount",self._vc_dismount)
        self._add_btn("Open Vault Dir",    self._open_vault)

    def _populate(self) -> None:
        vault_dir = self._mod.get("vault_dir", "")
        tool_rows = [
            (name, "✓ installed" if shutil.which(binary) else "✗ not found")
            for binary, name in _TOOLS
        ]
        rows = [("Vault dir", vault_dir)] + tool_rows
        self._set_info(rows)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _gpg_list(self) -> None:
        self._run_cmd(["gpg", "--list-keys"])

    def _gpg_gen(self) -> None:
        self._not_implemented("GPG key generation")

    def _age_new_key(self) -> None:
        self._not_implemented("age key generation")

    def _encrypt(self) -> None:
        self._not_implemented("File encryption dialog")

    def _decrypt(self) -> None:
        self._not_implemented("File decryption dialog")

    def _kp_list(self) -> None:
        self._not_implemented("KeePassXC list")

    def _vc_mount(self) -> None:
        self._not_implemented("VeraCrypt mount")

    def _vc_dismount(self) -> None:
        self._not_implemented("VeraCrypt dismount")

    def _open_vault(self) -> None:
        import os
        vault_dir = self._mod.get("vault_dir", "")
        if vault_dir:
            from nexus.core.platform import open_path
            open_path(vault_dir)
        else:
            self._append("[error] Vault dir not configured.")
