---
description: Security invariants, injection prevention rules, and safe path handling — applies to all code
paths:
  - "nexus/**"
  - "modules/**"
---

## Security Invariants

These must not be broken when modifying any code in this repo.

### Credential handling

- GitHub tokens are injected into HTTPS clone URLs at clone time only; never written to logs (`display_url` kept separate from the injected URL in `git_ops.py`).
- SSH clone URLs bypass token injection — auth is handled by the system SSH agent.
- `config/settings.yaml` and `projects/` are git-ignored — credentials never leave the machine via git.
- HA long-lived access token is passed via `httpx` headers — never appears in subprocess args visible in `ps aux`.
- All user-supplied paths go through `Path.expanduser()` before use.
- Secrets (stream keys, API tokens) belong in the Vault module, not plain-text project files.

### Shell injection prevention

- **LocalAI**: `{prompt}` / `{negative_prompt}` → `$NEXUS_PROMPT` / `$NEXUS_NEGATIVE_PROMPT` in the command string, passed via subprocess `env=` dict. Never interpolate user input directly into shell strings.
- **SDForge `launch_args`**: split with `shlex.split()`, passed as individual args to `asyncio.create_subprocess_exec` — not via `create_subprocess_shell`.
- No `shell=True` with any user-supplied data, ever.

### Path containment

- `VaultProjectScreen._validate_file_in_vault()` resolves both vault dir and user-supplied path with `Path.resolve()` and checks `startswith(vault_dir + "/")` before passing to `age` or `gpg` — prevents path traversal (`../../../../etc/shadow`).
- All restic paths go through `_p()` (`os.path.abspath(os.path.expanduser(path))`) in `backup_ops.py`.

### Subprocess safety

- Always use `asyncio.create_subprocess_exec` (arg list) rather than `create_subprocess_shell` (string) for any command that includes config-file or user-supplied values.
- `docker_ops.is_available()` runs `docker ps` to confirm the daemon is reachable — not just that the binary exists.
- `LocalAIProjectScreen._open_docker()` checks `is_symlink()` and refuses to mount symlinked paths into Docker.

### Key extraction

- `age-keygen -y <keyfile>` extracts the public key from an age identity file. Do not parse comment lines — fragile and removed.

### Backup initialisation

- `backup_run_backup` skill calls `restic_ensure_initialized()` before every backup — AI-triggered backups on uninitialised repos initialise automatically, never fail silently.
- `restic_ensure_initialized()` treats "already initialized" as success.

## What Claude Should Not Do

- Do not add `shell=True` to any subprocess call that touches user-controlled strings.
- Do not log API keys, tokens, or passwords — even at DEBUG level.
- Do not write credentials to any file outside `config/settings.yaml` (which is git-ignored).
- Do not skip the `_validate_file_in_vault()` guard when adding new vault operations.
