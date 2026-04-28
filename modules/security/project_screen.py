from __future__ import annotations
import shutil
from pathlib import Path

from textual.widgets import Label, Button, Log
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.ui.base_project_screen import BaseProjectScreen, _screen_css

log = get("security.project_screen")

_TOOLS = [
    ("ufw",             "ufw",           "Firewall frontend"),
    ("wg",              "wireguard-tools","WireGuard CLI"),
    ("openvpn",         "openvpn",       "OpenVPN daemon"),
    ("mullvad",         "mullvad-vpn",   "Mullvad CLI"),
    ("protonvpn-cli",   "protonvpn",     "ProtonVPN CLI"),
    ("fail2ban-client", "fail2ban",      "Brute-force protection"),
    ("lynis",           "lynis",         "System hardening audit"),
    ("nmap",            "nmap",          "Network scanner"),
    ("dnscrypt-proxy",  "dnscrypt-proxy","Encrypted DNS"),
    ("macchanger",      "macchanger",    "MAC address spoofing"),
    ("torsocks",        "torsocks",      "Tor proxy wrapper"),
]


class SecurityProjectScreen(BaseProjectScreen):
    MODULE_KEY   = "security"
    MODULE_LABEL = "SECURITY"
    SETUP_FIELDS = [
        {"id": "vpn_provider",    "label": "VPN provider (wireguard / openvpn / mullvad / protonvpn / custom)",
         "placeholder": "wireguard"},
        {"id": "vpn_config_dir",  "label": "VPN config directory",
         "placeholder": "~/.config/wireguard", "type": "dir"},
        {"id": "wireguard_iface", "label": "WireGuard interface name (optional)",
         "placeholder": "wg0", "optional": True},
        {"id": "dns_mode",        "label": "DNS privacy mode (system / dnscrypt / pihole / doh)",
         "placeholder": "system", "optional": True},
    ]

    DEFAULT_CSS = _screen_css("SecurityProjectScreen") + """
    .tool-row  { height: 1; }
    .tool-name { color: #E0E0FF; width: 20; }
    .tool-pkg  { color: #8080AA; width: 18; }
    .tool-desc { color: #555588; width: 1fr; }
    """

    # ── Action buttons ────────────────────────────────────────────────────────

    def _compose_action_buttons(self) -> list:
        return [
            Button("Firewall Status", id="btn-fw-status",  variant="primary"),
            Button("VPN Connect",     id="btn-vpn-up"),
            Button("VPN Disconnect",  id="btn-vpn-down"),
            Button("VPN Status",      id="btn-vpn-status"),
            Button("Open Ports",      id="btn-ports"),
            Button("DNS Check",       id="btn-dns-check"),
            Button("Fail2ban",        id="btn-fail2ban"),
            Button("System Audit",    id="btn-audit"),
            Button("Public IP",       id="btn-pubip"),
        ]

    # ── Primary folder ────────────────────────────────────────────────────────

    def _primary_folder(self) -> Path | None:
        raw = self._mod.get("vpn_config_dir", "").strip()
        if not raw:
            return None
        p = Path(raw).expanduser()
        return p if str(p) != "." else None

    # ── Content pane ──────────────────────────────────────────────────────────

    async def _populate_content(self) -> None:
        area = self.query_one("#content-area", Vertical)
        await area.remove_children()

        vpn_provider  = self._mod.get("vpn_provider", "wireguard").strip()
        vpn_config_dir = self._mod.get("vpn_config_dir", "").strip()
        iface         = self._mod.get("wireguard_iface", "").strip() or "wg0"
        dns_mode      = self._mod.get("dns_mode", "system").strip() or "system"

        widgets: list = []

        # ── Tool inventory ────────────────────────────────────────────────────
        widgets.append(Label("Installed tools:", classes="section-label"))
        for binary, pkg, purpose in _TOOLS:
            found = shutil.which(binary) is not None
            mark  = "✓" if found else "✗"
            cls   = "tool-row " + ("status-ok" if found else "status-err")
            widgets.append(
                Horizontal(
                    Label(f"  {mark} {binary}", classes="tool-name"),
                    Label(pkg,     classes="tool-pkg"),
                    Label(purpose, classes="tool-desc"),
                    classes=cls,
                )
            )

        # ── WireGuard interface status ────────────────────────────────────────
        widgets.append(Label(f"WireGuard interface ({iface}):", classes="section-label"))
        net_path = Path(f"/sys/class/net/{iface}")
        if net_path.exists():
            operstate_path = net_path / "operstate"
            state = operstate_path.read_text().strip() if operstate_path.exists() else "unknown"
            widgets.append(
                Horizontal(
                    Label("  Status:", classes="info-key"),
                    Label(state, classes="info-val status-ok"),
                    classes="info-row",
                )
            )
        else:
            widgets.append(
                Horizontal(
                    Label("  Status:", classes="info-key"),
                    Label("interface not found / down", classes="info-val status-err"),
                    classes="info-row",
                )
            )

        # ── Firewall status ───────────────────────────────────────────────────
        widgets.append(Label("Firewall (ufw):", classes="section-label"))
        ufw_conf = Path("/etc/ufw/ufw.conf")
        if ufw_conf.exists():
            try:
                enabled = any(
                    line.strip().upper() == "ENABLED=YES"
                    for line in ufw_conf.read_text(errors="replace").splitlines()
                    if not line.startswith("#")
                )
                fw_text = "Active"   if enabled else "Inactive"
                fw_cls  = "info-val status-ok" if enabled else "info-val status-err"
            except Exception:
                fw_text, fw_cls = "Unknown", "info-val hint"
        else:
            fw_text = "ufw not installed or /etc/ufw/ufw.conf not found"
            fw_cls  = "info-val hint"
        widgets.append(
            Horizontal(
                Label("  UFW:", classes="info-key"),
                Label(fw_text, classes=fw_cls),
                classes="info-row",
            )
        )

        # ── DNS resolvers ─────────────────────────────────────────────────────
        widgets.append(Label("DNS resolvers (/etc/resolv.conf):", classes="section-label"))
        resolv = Path("/etc/resolv.conf")
        if resolv.exists():
            try:
                ns_lines = [
                    line.split()[1]
                    for line in resolv.read_text(errors="replace").splitlines()
                    if line.startswith("nameserver") and len(line.split()) >= 2
                ]
                for ns in ns_lines[:4]:
                    widgets.append(
                        Horizontal(
                            Label("  nameserver:", classes="info-key"),
                            Label(ns, classes="info-val"),
                            classes="info-row",
                        )
                    )
                if not ns_lines:
                    widgets.append(Label("  (no nameservers found)", classes="hint"))
            except Exception:
                widgets.append(Label("  (could not read /etc/resolv.conf)", classes="hint"))
        else:
            widgets.append(Label("  /etc/resolv.conf not found", classes="hint"))

        # ── Config summary ────────────────────────────────────────────────────
        widgets.append(Label("Configuration:", classes="section-label"))
        cfg_path   = Path(vpn_config_dir).expanduser() if vpn_config_dir else None
        cfg_exists = cfg_path.exists() if cfg_path else False
        cfg_label  = (str(cfg_path) if cfg_path else "(not set)") + (" ✓" if cfg_exists else " (not found)")
        widgets.append(
            Horizontal(
                Label("  VPN config dir:", classes="info-key"),
                Label(cfg_label, classes="info-val " + ("status-ok" if cfg_exists else "hint")),
                classes="info-row",
            )
        )
        widgets.append(
            Horizontal(
                Label("  Provider:", classes="info-key"),
                Label(vpn_provider, classes="info-val"),
                classes="info-row",
            )
        )
        widgets.append(
            Horizontal(
                Label("  DNS mode:", classes="info-key"),
                Label(dns_mode, classes="info-val"),
                classes="info-row",
            )
        )

        # ── Hint ──────────────────────────────────────────────────────────────
        widgets.append(Label(
            "Note: some commands require sudo — configure NOPASSWD or run nexus with sudo.",
            classes="hint",
        ))

        await area.mount(*widgets)

    # ── Button handler ────────────────────────────────────────────────────────

    def _handle_action(self, bid: str | None) -> None:
        if not bid:
            return

        provider = self._mod.get("vpn_provider", "wireguard").strip()
        iface    = self._mod.get("wireguard_iface", "").strip() or "wg0"
        cfg_dir  = self._mod.get("vpn_config_dir", "").strip()

        if bid == "btn-fw-status":
            if shutil.which("ufw"):
                self.run_worker(self._run_cmd(["sudo", "ufw", "status", "verbose"]))
            else:
                self.run_worker(self._run_cmd(["sudo", "nft", "list", "ruleset"]))

        elif bid == "btn-vpn-up":
            if provider == "wireguard":
                self.run_worker(self._run_cmd(["sudo", "wg-quick", "up", iface]))
            elif provider == "openvpn":
                ovpn = self._first_ovpn(cfg_dir)
                if ovpn:
                    self.run_worker(self._run_cmd(["sudo", "openvpn", "--config", ovpn]))
                else:
                    self.app.notify("No .ovpn file found in config dir.", severity="error")
            elif provider == "mullvad":
                self.run_worker(self._run_cmd(["mullvad", "connect"]))
            elif provider == "protonvpn":
                self.run_worker(self._run_cmd(["protonvpn-cli", "connect", "--fastest"]))
            else:
                self.app.notify(f"Unknown provider: {provider}", severity="warning")

        elif bid == "btn-vpn-down":
            if provider == "wireguard":
                self.run_worker(self._run_cmd(["sudo", "wg-quick", "down", iface]))
            elif provider == "openvpn":
                self.run_worker(self._run_cmd(["sudo", "killall", "openvpn"]))
            elif provider == "mullvad":
                self.run_worker(self._run_cmd(["mullvad", "disconnect"]))
            elif provider == "protonvpn":
                self.run_worker(self._run_cmd(["protonvpn-cli", "disconnect"]))
            else:
                self.app.notify(f"Unknown provider: {provider}", severity="warning")

        elif bid == "btn-vpn-status":
            if provider == "wireguard":
                self.run_worker(self._run_cmd(["sudo", "wg", "show"]))
            elif provider == "mullvad":
                self.run_worker(self._run_cmd(["mullvad", "status"]))
            elif provider == "protonvpn":
                self.run_worker(self._run_cmd(["protonvpn-cli", "status"]))
            else:
                self.run_worker(self._run_cmd(["sudo", "systemctl", "status", "openvpn"]))

        elif bid == "btn-ports":
            self.run_worker(self._run_cmd(["ss", "-tulnp"]))

        elif bid == "btn-dns-check":
            self.run_worker(self._dns_check_sequence())

        elif bid == "btn-fail2ban":
            self.run_worker(self._run_cmd(["sudo", "fail2ban-client", "status"]))

        elif bid == "btn-audit":
            self.run_worker(self._run_cmd(
                ["sudo", "lynis", "audit", "system", "--quick", "--no-colors"]
            ))

        elif bid == "btn-pubip":
            self.run_worker(self._fetch_public_ip())

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _first_ovpn(cfg_dir: str) -> str | None:
        if not cfg_dir:
            return None
        p = Path(cfg_dir).expanduser()
        for f in sorted(p.glob("*.ovpn")):
            return str(f)
        return None

    async def _dns_check_sequence(self) -> None:
        await self._run_cmd(["cat", "/etc/resolv.conf"])
        if shutil.which("resolvectl"):
            await self._run_cmd(["resolvectl", "status"])

    async def _fetch_public_ip(self) -> None:
        import httpx
        try:
            ui_log = self.query_one("#output-log", Log)
        except Exception:
            return
        try:
            ui_log.write_line("Contacting api.ipify.org (external server)…")
        except Exception:
            return
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get("https://api.ipify.org")
            ip = resp.text.strip()
            try:
                ui_log.write_line(f"Public IP: {ip}")
            except Exception:
                pass
        except httpx.ConnectError:
            try:
                ui_log.write_line("✗ Cannot connect to api.ipify.org")
            except Exception:
                pass
        except Exception as exc:
            log.exception("Public IP fetch failed")
            try:
                ui_log.write_line(f"✗ {exc}")
            except Exception:
                pass
