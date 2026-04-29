from __future__ import annotations
import asyncio
import json
from pathlib import Path

from nexus.ai.skill_registry import registry, require_project
from nexus.core.logger import get

log = get("skills.vault")

_AGE_KEY = Path.home() / ".age" / "key.txt"


def _vault_cfg(slug: str) -> dict:
    return require_project(slug).get("vault", {})


async def _get_age_pubkey(key_path: Path) -> str:
    """Return the age public key for key_path using age-keygen -y, with comment fallback."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "age-keygen", "-y", str(key_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await proc.communicate()
        if proc.returncode == 0:
            return out.decode().strip()
    except FileNotFoundError:
        pass
    try:
        text = await asyncio.to_thread(key_path.read_text, errors="replace")
        for line in text.splitlines():
            if line.startswith("# public key:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return ""


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
    pubkey = await _get_age_pubkey(_AGE_KEY) if exists else ""
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
    vault_raw = _vault_cfg(slug).get("vault_dir", "")
    if vault_raw:
        vault_dir = Path(vault_raw).expanduser().resolve()
        if not file_path.resolve().is_relative_to(vault_dir):
            return json.dumps({"error": "path must be inside the configured vault directory"})
    if not _AGE_KEY.exists():
        return json.dumps({"error": "age key not found at ~/.age/key.txt. Generate one first."})
    if not file_path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})
    pubkey = await _get_age_pubkey(_AGE_KEY)
    if not pubkey:
        return json.dumps({"error": "Could not derive public key from age key file"})
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


# ---------------------------------------------------------------------------
# vault_decrypt_file
# ---------------------------------------------------------------------------

async def _vault_decrypt_file(args: dict) -> str:
    slug      = args["project_slug"]
    file_path = Path(args["path"]).expanduser()
    engine    = args.get("engine", "age")
    vault_raw = _vault_cfg(slug).get("vault_dir", "")
    if vault_raw:
        vault_dir = Path(vault_raw).expanduser().resolve()
        if not file_path.resolve().is_relative_to(vault_dir):
            return json.dumps({"error": "path must be inside the configured vault directory"})
    if not file_path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})

    if engine == "age":
        if not _AGE_KEY.exists():
            return json.dumps({"error": "age key not found at ~/.age/key.txt"})
        suffix = file_path.suffix
        out_path = file_path.with_suffix("") if suffix == ".age" else file_path.with_suffix(".dec")
        try:
            proc = await asyncio.create_subprocess_exec(
                "age", "--decrypt", "-i", str(_AGE_KEY), "-o", str(out_path), str(file_path),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            )
            out, _ = await proc.communicate()
            ok = proc.returncode == 0
            return json.dumps({"success": ok, "output_path": str(out_path),
                               "output": out.decode(errors="replace").strip()})
        except FileNotFoundError:
            return json.dumps({"error": "age not found on PATH"})
        except Exception as exc:
            log.exception("vault_decrypt_file (age) skill failed")
            return json.dumps({"error": str(exc)})

    elif engine == "gpg":
        out_path = file_path.with_suffix("") if file_path.suffix == ".gpg" else \
                   file_path.with_suffix(".dec")
        try:
            proc = await asyncio.create_subprocess_exec(
                "gpg", "--decrypt", "--output", str(out_path), str(file_path),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            )
            out, _ = await proc.communicate()
            ok = proc.returncode == 0
            return json.dumps({"success": ok, "output_path": str(out_path),
                               "output": out.decode(errors="replace").strip()})
        except FileNotFoundError:
            return json.dumps({"error": "gpg not found on PATH"})
        except Exception as exc:
            log.exception("vault_decrypt_file (gpg) skill failed")
            return json.dumps({"error": str(exc)})

    return json.dumps({"error": f"Unknown engine: {engine}. Use 'age' or 'gpg'."})


registry.register(
    scope       = "vault",
    name        = "vault_decrypt_file",
    description = "Decrypt a file using age or gpg. Returns the path to the decrypted output file.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "path":         {"type": "string", "description": "Absolute or ~ path to the encrypted file"},
            "engine":       {"type": "string", "enum": ["age", "gpg"],
                             "description": "Decryption engine: 'age' (default) or 'gpg'"},
        },
        "required": ["project_slug", "path"],
    },
    handler = _vault_decrypt_file,
)
