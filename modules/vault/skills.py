from __future__ import annotations
import asyncio
import json
from pathlib import Path

from nexus.ai.skill_registry import registry
from nexus.core.config_manager import load_project_config
from nexus.core.logger import get

log = get("skills.vault")

_AGE_KEY = Path.home() / ".age" / "key.txt"


def _vault_cfg(slug: str) -> dict:
    return load_project_config(slug).get("vault", {})


# ---------------------------------------------------------------------------
# vault_list_gpg_keys
# ---------------------------------------------------------------------------

async def _vault_list_gpg_keys(args: dict) -> str:
    try:
        proc = await asyncio.create_subprocess_exec(
            "gpg", "--list-keys",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await proc.communicate()
        return json.dumps({"output": out.decode(errors="replace").strip(),
                           "returncode": proc.returncode})
    except FileNotFoundError:
        return json.dumps({"error": "gpg not found on PATH"})
    except Exception as exc:
        log.exception("vault_list_gpg_keys skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "vault",
    name        = "vault_list_gpg_keys",
    description = "List all GPG public keys in the local keyring.",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _vault_list_gpg_keys,
)


# ---------------------------------------------------------------------------
# vault_age_key_status
# ---------------------------------------------------------------------------

async def _vault_age_key_status(args: dict) -> str:
    exists = _AGE_KEY.exists()
    pubkey = ""
    if exists:
        for line in _AGE_KEY.read_text(errors="replace").splitlines():
            if line.startswith("# public key:"):
                pubkey = line.split(":", 1)[1].strip()
                break
    return json.dumps({"key_exists": exists, "key_path": str(_AGE_KEY), "public_key": pubkey})


registry.register(
    scope       = "vault",
    name        = "vault_age_key_status",
    description = "Check whether an age key exists at ~/.age/key.txt and return its public key.",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _vault_age_key_status,
)


# ---------------------------------------------------------------------------
# vault_encrypt_file
# ---------------------------------------------------------------------------

async def _vault_encrypt_file(args: dict) -> str:
    slug      = args["project_slug"]
    file_path = Path(args["path"]).expanduser()
    if not _AGE_KEY.exists():
        return json.dumps({"error": "age key not found at ~/.age/key.txt. Generate one first."})
    if not file_path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})
    pubkey = ""
    for line in _AGE_KEY.read_text(errors="replace").splitlines():
        if line.startswith("# public key:"):
            pubkey = line.split(":", 1)[1].strip()
            break
    if not pubkey:
        return json.dumps({"error": "Could not read public key from age key file"})
    out_path = file_path.with_suffix(file_path.suffix + ".age")
    try:
        proc = await asyncio.create_subprocess_exec(
            "age", "-r", pubkey, "-o", str(out_path), str(file_path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await proc.communicate()
        ok = proc.returncode == 0
        return json.dumps({"success": ok, "output_path": str(out_path),
                           "output": out.decode(errors="replace").strip()})
    except FileNotFoundError:
        return json.dumps({"error": "age not found on PATH"})
    except Exception as exc:
        log.exception("vault_encrypt_file skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "vault",
    name        = "vault_encrypt_file",
    description = "Encrypt a file using the age key at ~/.age/key.txt. Produces <file>.age alongside the original.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "path":         {"type": "string", "description": "Absolute or ~ path to the file to encrypt"},
        },
        "required": ["project_slug", "path"],
    },
    handler = _vault_encrypt_file,
)
