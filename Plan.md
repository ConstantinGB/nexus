# Security Module — Implementation Plan

## Context

New Nexus module for network security, privacy, and anti-surveillance tooling.
Covers: firewalls, VPNs, DNS privacy, open-port auditing, intrusion detection,
system hardening, and anonymization tools.

---

## 1 — Module Registration

### `nexus/core/module_manager.py`

**Add to `_REGISTRY`** (after vault entry):

```python
ModuleInfo("security", "Security", "Firewall, VPN, DNS privacy and system hardening", ["security", "privacy", "network"]),
```

**Add to `MODULE_PREFIX`**:

```python
"security": "sec",
```

**Add to `get_project_screen()`** (same pattern as vault):

```python
elif project.module == "security":
    from modules.security.project_screen import SecurityProjectScreen
    return SecurityProjectScreen(project)
```

**Add to `_MODULE_DISPLAY` in `nexus/ui/tiles.py`**:

```python
"security": "Security",
```

---

## 2 — File Structure

Create directory `modules/security/` with:

```text
modules/security/
  __init__.py          (empty)
  project_screen.py    (main UI)
  skills.py            (AI skills)
  CLAUDE.template.md   (project template)
```

No multi-step setup screen needed — inline SETUP_FIELDS is sufficient.

---

## 3 — `modules/security/project_screen.py`

### Class skeleton

```python
class SecurityProjectScreen(BaseProjectScreen):
    MODULE_KEY   = "security"
    MODULE_LABEL = "SECURITY"
    SETUP_FIELDS = [
        {"id": "vpn_provider",    "label": "VPN provider (wireguard / openvpn / mullvad / protonvpn / custom)",
         "placeholder": "wireguard"},
        {"id": "vpn_config_dir", "label": "VPN config directory",
         "placeholder": "~/.config/wireguard", "type": "dir"},
        {"id": "wireguard_iface","label": "WireGuard interface name (optional)",
         "placeholder": "wg0", "optional": True},
        {"id": "dns_mode",       "label": "DNS privacy mode (system / dnscrypt / pihole / doh)",
         "placeholder": "system", "optional": True},
    ]
```

### Action buttons

```python
def _compose_action_buttons(self) -> list:
    return [
        Button("Firewall Status",   id="btn-fw-status",   variant="primary"),
        Button("VPN Connect",       id="btn-vpn-up"),
        Button("VPN Disconnect",    id="btn-vpn-down"),
        Button("VPN Status",        id="btn-vpn-status"),
        Button("Open Ports",        id="btn-ports"),
        Button("DNS Check",         id="btn-dns-check"),
        Button("Fail2ban",          id="btn-fail2ban"),
        Button("System Audit",      id="btn-audit"),
        Button("Public IP",         id="btn-pubip"),
    ]
```

### Content pane (`_populate_content`)

Display in `#content-area`:

**Tool inventory** — check each with `shutil.which()`:

| Tool | Package | Purpose |
| --- | --- | --- |
| `ufw` | ufw | Firewall frontend |
| `wg` | wireguard-tools | WireGuard CLI |
| `openvpn` | openvpn | OpenVPN daemon |
| `mullvad` | mullvad-vpn | Mullvad CLI |
| `protonvpn-cli` | protonvpn | ProtonVPN CLI |
| `fail2ban-client` | fail2ban | Brute-force protection |
| `lynis` | lynis | System hardening audit |
| `nmap` | nmap | Network scanner |
| `dnscrypt-proxy` | dnscrypt-proxy | Encrypted DNS |
| `macchanger` | macchanger | MAC address spoofing |
| `torsocks` | torsocks | Tor proxy wrapper |

**WireGuard interface status** — `wg show <iface>` parsed:

- Interface up/down (status-ok / status-err class)
- Peer count, latest handshake time

**Firewall status** — `ufw status` single-line:

- Active / Inactive (status-ok / status-err class)

**DNS resolver** — read `/etc/resolv.conf`, show `nameserver` lines.

**Config dir info** — path + whether it exists.

**Hint label** — `"Note: some commands require sudo — configure NOPASSWD or run with sudo."`

### Button handler (`_handle_action`)

```python
"btn-fw-status"  → _run_cmd(["sudo", "ufw", "status", "verbose"])
                   (fall back to nft if ufw not found)

"btn-vpn-up"     → dispatch on vpn_provider:
                     wireguard  → _run_cmd(["sudo", "wg-quick", "up", iface])
                     openvpn    → _run_cmd(["sudo", "openvpn", "--config", first_ovpn_in_dir])
                     mullvad    → _run_cmd(["mullvad", "connect"])
                     protonvpn  → _run_cmd(["protonvpn-cli", "connect", "--fastest"])

"btn-vpn-down"   → dispatch on vpn_provider:
                     wireguard  → _run_cmd(["sudo", "wg-quick", "down", iface])
                     openvpn    → _run_cmd(["sudo", "killall", "openvpn"])
                     mullvad    → _run_cmd(["mullvad", "disconnect"])
                     protonvpn  → _run_cmd(["protonvpn-cli", "disconnect"])

"btn-vpn-status" → dispatch on vpn_provider:
                     wireguard  → _run_cmd(["sudo", "wg", "show"])
                     mullvad    → _run_cmd(["mullvad", "status"])
                     protonvpn  → _run_cmd(["protonvpn-cli", "status"])
                     openvpn    → _run_cmd(["sudo", "systemctl", "status", "openvpn"])

"btn-ports"      → _run_cmd(["ss", "-tulnp"])

"btn-dns-check"  → _run_cmd(["cat", "/etc/resolv.conf"])
                   then also _run_cmd(["resolvectl", "status"]) if available

"btn-fail2ban"   → _run_cmd(["sudo", "fail2ban-client", "status"])

"btn-audit"      → _run_cmd(["sudo", "lynis", "audit", "system", "--quick", "--no-colors"])

"btn-pubip"      → async httpx GET https://api.ipify.org
                   write "Contacting api.ipify.org (external server)..." warning first
                   then write the returned IP to the log
```

---

## 4 — `modules/security/skills.py`

Register 4 skills under scope `"security"`:

```python
registry.register(
    scope="security", name="security_firewall_status",
    description="Show current firewall rules (ufw or nftables).",
    schema={"type": "object", "properties": {"project_slug": {"type": "string"}}, "required": ["project_slug"]},
    handler=_firewall_status,
)

registry.register(
    scope="security", name="security_vpn_status",
    description="Check VPN connection state for this project's configured provider.",
    schema={"type": "object", "properties": {"project_slug": {"type": "string"}}, "required": ["project_slug"]},
    handler=_vpn_status,
)

registry.register(
    scope="security", name="security_open_ports",
    description="List open listening ports using ss.",
    schema={"type": "object", "properties": {"project_slug": {"type": "string"}}, "required": ["project_slug"]},
    handler=_open_ports,
)

registry.register(
    scope="security", name="security_dns_check",
    description="Show current DNS resolver configuration.",
    schema={"type": "object", "properties": {"project_slug": {"type": "string"}}, "required": ["project_slug"]},
    handler=_dns_check,
)
```

Each handler: load project config via `load_project_config(slug)` → run subprocess → return stdout as string.

---

## 5 — `modules/security/CLAUDE.template.md`

Sections to include:

- **Title**: `# {project_name} — Security`
- **Key software**: ufw, WireGuard/wg-quick, OpenVPN, Mullvad, ProtonVPN, fail2ban, lynis, dnscrypt-proxy, nmap, ss, macchanger, torsocks — each with typical commands
- **Security principles**: least-privilege firewall, encrypted DNS, VPN kill-switch, regular audits, VPN vs Tor threat model distinction
- **WireGuard kill-switch with ufw**: example rule set (default deny → allow only via wg0 → allow VPN server UDP 51820)
- **Typical AI tasks**: write ufw rule sets, generate WireGuard configs, audit resolv.conf, explain lynis findings, write fail2ban jails
- **Your setup** (comment placeholders): VPN provider, WireGuard interface, DNS strategy, threat model, exposed services
- **Notes for the AI** (comment placeholder)

---

## 6 — Register skills at startup

In `nexus/app.py`, add alongside other module skill imports:

```python
from modules.security import skills as _security_skills  # noqa: F401
```

---

## 7 — Verification

```bash
python -m py_compile modules/security/project_screen.py
python -m py_compile modules/security/skills.py
python -m py_compile nexus/core/module_manager.py
python -m py_compile nexus/ui/tiles.py
python -c "from modules.security.project_screen import SecurityProjectScreen; print('OK')"
uv run nexus
```

Manual checks:

- "Add Project" tile grid shows Security module with correct tile label
- Create a `sec-test` project → inline setup form shows 4 fields; Browse works on VPN config dir
- After saving setup → content pane shows tool inventory (✓/✗), WG status, firewall status, DNS nameservers
- Firewall Status button → output log shows ufw output
- VPN Connect / Disconnect → wg-quick output appears in log
- Open Ports → `ss -tulnp` output in log
- Public IP → external-server warning then IP address in log
