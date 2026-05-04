from __future__ import annotations

import shutil
from nexus.core.project_manager import ProjectInfo
from nexus.ui.gui.module_base import ModuleGuiBase

log = __import__("nexus.core.logger", fromlist=["get"]).get("security.gui_screen")

_TOOLS = [("ufw", "UFW"), ("nmap", "Nmap"), ("fail2ban-client", "Fail2ban"),
          ("openvpn", "OpenVPN"), ("lynis", "Lynis")]


class GuiScreen(ModuleGuiBase):
    SKILL_SCOPES = None  # no chat panel per plan

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"Security — {project.name}")
        self._mod = self._cfg.get("security", {})
        self._populate()

    def _build_toolbar(self) -> None:
        self._add_btn("Firewall Status", self._fw_status,  primary=True)
        self._add_btn("VPN Connect",     self._vpn_up)
        self._add_btn("VPN Disconnect",  self._vpn_down)
        self._add_btn("VPN Status",      self._vpn_status)
        self._add_btn("Open Ports",      self._open_ports)
        self._add_btn("DNS Check",       self._dns_check)
        self._add_btn("Fail2ban",        self._fail2ban)
        self._add_btn("System Audit",    self._audit)
        self._add_btn("Public IP",       self._pubip)

    def _populate(self) -> None:
        tool_rows = [
            (name, "✓" if shutil.which(binary) else "✗ not found")
            for binary, name in _TOOLS
        ]
        vpn = self._mod.get("vpn_interface", "")
        self._set_info([("VPN interface", vpn or "(not set)")] + tool_rows)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _fw_status(self) -> None:
        self._run_cmd(["sudo", "ufw", "status", "verbose"] if shutil.which("ufw")
                      else ["iptables", "-L", "-n"])

    def _vpn_up(self) -> None:
        iface = self._mod.get("vpn_interface", "")
        if not iface:
            self._append("[error] VPN interface not configured.")
            return
        self._run_cmd(["sudo", "wg-quick", "up", iface])

    def _vpn_down(self) -> None:
        iface = self._mod.get("vpn_interface", "")
        if not iface:
            self._append("[error] VPN interface not configured.")
            return
        self._run_cmd(["sudo", "wg-quick", "down", iface])

    def _vpn_status(self) -> None:
        self._run_cmd(["sudo", "wg", "show"] if shutil.which("wg")
                      else ["ip", "link", "show"])

    def _open_ports(self) -> None:
        self._run_cmd(["ss", "-tlnp"])

    def _dns_check(self) -> None:
        self._run_cmd(["dig", "+short", "myip.opendns.com", "@resolver1.opendns.com"]
                      if shutil.which("dig") else ["nslookup", "google.com"])

    def _fail2ban(self) -> None:
        self._run_cmd(["sudo", "fail2ban-client", "status"] if shutil.which("fail2ban-client")
                      else ["echo", "fail2ban not installed"])

    def _audit(self) -> None:
        if shutil.which("lynis"):
            self._run_cmd(["sudo", "lynis", "audit", "system", "--quick"])
        else:
            self._append("[error] lynis not found.")

    def _pubip(self) -> None:
        self._run_cmd(["curl", "-s", "https://api.ipify.org"])
