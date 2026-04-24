# {project_name} — Server

This project manages one or more self-hosted servers or services. Servers may be game
servers, web servers, media servers, or self-hosted applications. The AI helps with
installation, configuration, systemd services, firewalling, reverse proxies, and debugging.

## Key software

### Service management
- **systemd** — `systemctl start/stop/restart/status/enable/disable <service>`
- **journalctl** — logs: `journalctl -u <service> -f` (follow), `-n 100` (last 100 lines)
- **Docker + Docker Compose** — `docker compose up -d`, `docker logs -f <name>`, `docker exec -it <name> bash`

### Networking & security
- **ufw** — simple firewall: `ufw allow 80/tcp`, `ufw status numbered`, `ufw enable`
- **Caddy** — reverse proxy with automatic HTTPS; config in `Caddyfile`
- **nginx** — reverse proxy / web server; vhosts in `/etc/nginx/sites-available/`
- **certbot** — Let's Encrypt TLS certificates: `certbot --nginx -d example.com`
- **fail2ban** — block brute-force IPs: `fail2ban-client status`
- **ssh hardening** — disable password auth in `/etc/ssh/sshd_config`: `PasswordAuthentication no`

### Common server types
- **Minecraft** — `java -Xmx4G -jar server.jar nogui`; settings in `server.properties`
- **Valheim** — SteamCMD install; `valheim_server.x86_64 -name … -port 2456 -world …`
- **Jellyfin** — media server, port 8096; config at `~/.config/jellyfin/`
- **Nextcloud** — PHP/Apache or Docker; app config in `config/config.php`
- **Vaultwarden** — lightweight Bitwarden; Docker with `vaultwarden/server` image
- **Gitea / Forgejo** — self-hosted git forge; port 3000 by default

### Monitoring & maintenance
- **htop** — interactive process monitor
- **ss -tlnp** — list open TCP ports and their processes
- **rsync** — incremental file sync/backup: `rsync -avz src/ user@host:dest/`
- **restic** — encrypted, deduplicated backups: `restic backup ~/data --repo /mnt/backup`
- **borgbackup** — deduplicating archive backup: `borg create /repo::archive ~/data`

## Typical tasks

- Write or review a `docker-compose.yml` for a new service
- Create a systemd unit file for a custom or bare-metal application
- Configure a Caddy or nginx reverse proxy with a subdomain and TLS
- Open the correct firewall ports for a new service
- Debug a service that won't start: read `journalctl -u <service>` output
- Set up automated backups with rsync, restic, or borg
- Harden SSH and the firewall on a new server

## Caddy reverse proxy example

```caddy
example.com {
    reverse_proxy localhost:8096
}

git.example.com {
    reverse_proxy localhost:3000
}
```

## File and config conventions

- **`/etc/systemd/system/<name>.service`** — custom systemd unit files
- **`/etc/caddy/Caddyfile`** or local `Caddyfile` — Caddy config
- **`/etc/nginx/sites-available/<name>`** + symlink to `sites-enabled/` — nginx vhosts
- **`docker-compose.yml`** — Compose service definitions
- **`.env`** — environment variables for Compose (never commit secrets — use a vault)
- **`/var/log/`** — system logs; app logs often in Docker volumes

---

## Your setup

<!-- Server type(s) and purpose:
     e.g. Minecraft survival server, Jellyfin + Nextcloud homelab, personal VPS for web -->

<!-- Hosting: local machine / homelab hardware / VPS (provider: Hetzner / DigitalOcean / etc.) -->

<!-- Operating system and version: e.g. Ubuntu 24.04, Debian 12 -->

<!-- Domain name (if any): -->

<!-- Services and their ports:
     e.g. Jellyfin → 8096, Caddy → 80/443, Minecraft → 25565 -->

<!-- Container runtime: Docker Compose / Podman Compose / bare-metal -->

<!-- Backup strategy:
     e.g. nightly restic to Backblaze B2, weekly rsync to external drive -->

## Notes for the AI

<!-- Resource constraints (RAM/CPU), shared hosting restrictions,
     existing config not to touch, monitoring tools already in place. -->
