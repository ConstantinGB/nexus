from __future__ import annotations
import asyncio
import json
from pathlib import Path

from nexus.ai.skill_registry import registry, require_project
from nexus.core.logger import get

log = get("skills.security")


def _sec_cfg(slug: str) -> dict:
    return require_project(slug).get("security", {})


# ---------------------------------------------------------------------------
# security_firewall_status
# ---------------------------------------------------------------------------

async def _firewall_status(args: dict) -> str:
    import shutil
    cmd = (
        ["sudo", "ufw", "status", "verbose"]
        if shutil.which("ufw")
        else ["sudo", "nft", "list", "ruleset"]
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await proc.communicate()
        return json.dumps({
            "output": out.decode(errors="replace").strip(),
            "returncode": proc.returncode,
        })
    except FileNotFoundError:
        return json.dumps({"error": f"{cmd[1]} not found on PATH"})
    except Exception as exc:
        log.exception("security_firewall_status skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "security",
    name        = "security_firewall_status",
    description = "Show current firewall rules (ufw or nftables).",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _firewall_status,
)


# ---------------------------------------------------------------------------
# security_vpn_status
# ---------------------------------------------------------------------------

async def _vpn_status(args: dict) -> str:
    cfg      = _sec_cfg(args["project_slug"])
    provider = cfg.get("vpn_provider", "wireguard").strip()

    cmd_map = {
        "wireguard": ["sudo", "wg", "show"],
        "mullvad":   ["mullvad", "status"],
        "protonvpn": ["protonvpn-cli", "status"],
        "openvpn":   ["sudo", "systemctl", "status", "openvpn"],
    }
    cmd = cmd_map.get(provider, ["sudo", "wg", "show"])
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await proc.communicate()
        return json.dumps({
            "provider":   provider,
            "output":     out.decode(errors="replace").strip(),
            "returncode": proc.returncode,
        })
    except FileNotFoundError:
        return json.dumps({"error": f"{cmd[0]} not found on PATH"})
    except Exception as exc:
        log.exception("security_vpn_status skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "security",
    name        = "security_vpn_status",
    description = "Check VPN connection state for this project's configured provider.",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _vpn_status,
)


# ---------------------------------------------------------------------------
# security_open_ports
# ---------------------------------------------------------------------------

async def _open_ports(args: dict) -> str:
    try:
        proc = await asyncio.create_subprocess_exec(
            "ss", "-tulnp",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await proc.communicate()
        return json.dumps({
            "output":     out.decode(errors="replace").strip(),
            "returncode": proc.returncode,
        })
    except FileNotFoundError:
        return json.dumps({"error": "ss not found on PATH"})
    except Exception as exc:
        log.exception("security_open_ports skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "security",
    name        = "security_open_ports",
    description = "List open listening ports using ss.",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _open_ports,
)


# ---------------------------------------------------------------------------
# security_dns_check
# ---------------------------------------------------------------------------

async def _dns_check(args: dict) -> str:
    import shutil
    result: dict = {}

    resolv = Path("/etc/resolv.conf")
    result["resolv_conf"] = (
        resolv.read_text(errors="replace").strip() if resolv.exists() else "(not found)"
    )

    if shutil.which("resolvectl"):
        try:
            proc = await asyncio.create_subprocess_exec(
                "resolvectl", "status",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            out, _ = await proc.communicate()
            result["resolvectl"] = out.decode(errors="replace").strip()
        except Exception as exc:
            result["resolvectl_error"] = str(exc)

    return json.dumps(result)


registry.register(
    scope       = "security",
    name        = "security_dns_check",
    description = "Show current DNS resolver configuration.",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _dns_check,
)
