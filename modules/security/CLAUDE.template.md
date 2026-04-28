# {project_name} — Security

A security, privacy, and network-hardening project managed by Nexus.

---

## Key Software

### Firewall — ufw / nftables

```bash
sudo ufw status verbose          # show rules
sudo ufw enable / disable
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp            # open SSH
sudo ufw delete allow 22/tcp
sudo ufw reload
sudo nft list ruleset            # raw nftables (ufw uses nft internally)
```

### WireGuard — wg / wg-quick

```bash
sudo wg-quick up wg0             # bring interface up
sudo wg-quick down wg0
sudo wg show                     # live peer status
sudo wg show wg0 transfer        # bytes sent/received
wg genkey | tee privkey | wg pubkey > pubkey   # generate keypair
sudo systemctl enable --now wg-quick@wg0       # start on boot
```

### OpenVPN

```bash
sudo openvpn --config /etc/openvpn/client.ovpn
sudo systemctl start openvpn@client
sudo systemctl status openvpn
sudo journalctl -u openvpn -f    # live logs
```

### Mullvad VPN

```bash
mullvad status
mullvad connect / disconnect
mullvad relay list
mullvad relay set location se    # set country
mullvad dns set --default        # restore DNS
mullvad account get
```

### ProtonVPN

```bash
protonvpn-cli connect --fastest
protonvpn-cli connect --cc DE    # specific country
protonvpn-cli disconnect
protonvpn-cli status
protonvpn-cli s                  # short status
```

### fail2ban

```bash
sudo fail2ban-client status
sudo fail2ban-client status sshd
sudo fail2ban-client set sshd unbanip <ip>
sudo journalctl -u fail2ban -f
# Config: /etc/fail2ban/jail.local
```

### lynis — System Hardening Audit

```bash
sudo lynis audit system --quick --no-colors
sudo lynis audit system --tests-from-group networking
sudo lynis show details TEST-ID  # details for a specific finding
# Report: /var/log/lynis-report.dat
```

### nmap — Network Scanner

```bash
nmap -sV localhost                # service version detection
nmap -p- localhost                # all ports
sudo nmap -O 192.168.1.0/24      # OS detection on LAN
nmap --script vuln <target>       # vulnerability scan (authorised targets only)
```

### dnscrypt-proxy — Encrypted DNS

```bash
sudo systemctl start dnscrypt-proxy
sudo systemctl status dnscrypt-proxy
# Config: /etc/dnscrypt-proxy/dnscrypt-proxy.toml
# Set nameserver 127.0.0.1 in /etc/resolv.conf
```

### macchanger — MAC Address Spoofing

```bash
sudo macchanger -r eth0          # randomise MAC
sudo macchanger -s eth0          # show current/permanent MAC
sudo macchanger --mac=XX:XX:XX:XX:XX:XX eth0
```

### torsocks — Tor Proxy Wrapper

```bash
torsocks curl https://check.torproject.org
torsocks ssh user@host
# Requires: tor service running
sudo systemctl start tor
```

### ss / netstat — Port Auditing

```bash
ss -tulnp                        # listening TCP+UDP with process names
ss -tulnp | grep LISTEN
ss -s                            # summary statistics
```

---

## Security Principles

- **Least-privilege firewall**: default deny incoming, whitelist only what you expose.
- **Encrypted DNS**: avoid cleartext DNS; use dnscrypt-proxy, DoH, or a trusted resolver over a VPN tunnel.
- **VPN kill-switch**: ensure traffic cannot leak if the VPN drops — enforce via firewall rules.
- **Regular audits**: run `lynis` after system changes; review `fail2ban` jails and open ports periodically.
- **VPN vs Tor**: VPN hides traffic from your ISP and shifts trust to the VPN provider; Tor provides stronger anonymity at the cost of speed and exit-node trust issues. Do not assume a VPN makes you anonymous.
- **Minimal attack surface**: disable services not in use (`systemctl disable <service>`), close unused ports.

---

## WireGuard Kill-Switch with ufw

Prevent any traffic from leaving outside the WireGuard tunnel:

```bash
# 1. Default policies
sudo ufw default deny incoming
sudo ufw default deny outgoing

# 2. Allow loopback
sudo ufw allow in on lo
sudo ufw allow out on lo

# 3. Allow DNS inside tunnel (adjust if DNS server differs)
sudo ufw allow out on wg0

# 4. Allow the WireGuard handshake itself (UDP to your VPN server)
sudo ufw allow out to <vpn-server-ip> port 51820 proto udp

# 5. Allow established connections
sudo ufw allow in on wg0

sudo ufw enable
```

Result: if `wg0` goes down, all outbound traffic is blocked — no leak.

---

## Typical AI Tasks

- Write and explain ufw rule sets for specific threat models.
- Generate WireGuard client/server config files with kill-switch rules.
- Audit `/etc/resolv.conf` and explain current DNS privacy posture.
- Interpret `lynis` audit findings and suggest remediation steps.
- Write `fail2ban` jail configurations for custom services.
- Review open ports from `ss` output and identify unnecessary exposure.
- Design a threat model for this machine's network access.

---

## Your Setup

<!-- Fill in these details so the AI understands your environment -->

- **VPN provider**: <!-- wireguard / mullvad / protonvpn / openvpn / custom -->
- **WireGuard interface**: <!-- wg0 -->
- **VPN config directory**: <!-- ~/.config/wireguard or /etc/wireguard -->
- **DNS strategy**: <!-- system / dnscrypt / pihole / DoH via VPN -->
- **Threat model**: <!-- ISP privacy / public Wi-Fi / remote work / other -->
- **Exposed services**: <!-- SSH on port X / web server / none -->
- **OS / distro**: <!-- Ubuntu 24.04 / Arch / Fedora / etc. -->

---

## Notes for the AI

<!-- Add any additional context, constraints, or preferences here -->
