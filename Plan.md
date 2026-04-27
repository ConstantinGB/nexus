# Adversarial Review — Fix Plan

## Context

Four-agent adversarial review (security, async/races, error-handling, Docker-specific) found 16
confirmed bugs across the recent Docker integration and existing module code. Fixes are grouped
by theme and ordered by impact. No architectural changes — targeted patches only.

---

## Group 1 — `_run_cmd` base class: two bugs in one function

**File:** `nexus/ui/base_project_screen.py:352–373`

**Bug A — missed `assert proc.stdout`** (line 363): The previous audit fixed this in 5 files but
skipped the base class itself. Same failure mode: swallowed `AssertionError` under `-O`.

**Bug B — unguarded `query_one` (C1)**: `query_one("#output-log")` at line 353 raises `NoMatches`
if the user dismisses the screen while any worker is running `_run_cmd`. This is the root cause
for crashes in streaming, emulator, vault, home, and every other module using the base class.

**Fix — replace the entire method:**
```python
async def _run_cmd(self, cmd: list[str], cwd: str | None = None) -> None:
    try:
        ui_log = self.query_one("#output-log", Log)
    except Exception:
        return  # screen dismissed
    cmd_str = " ".join(str(c) for c in cmd)
    ui_log.write_line(f"$ {cmd_str}")
    try:
        proc = await asyncio.create_subprocess_exec(
            *[str(c) for c in cmd],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd,
        )
        if proc.stdout is None:
            log.error("subprocess stdout is None for %s", cmd)
            return
        async for raw in proc.stdout:
            try:
                ui_log.write_line(raw.decode(errors="replace").rstrip())
            except Exception:
                break  # screen dismissed mid-stream
        await proc.wait()
        try:
            ui_log.write_line(f"✓ Exited {proc.returncode}")
        except Exception:
            pass
    except FileNotFoundError:
        try:
            ui_log.write_line(f"✗ Not found: {cmd[0]}")
            self.app.notify(f"'{cmd[0]}' not found on PATH.", severity="error")
        except Exception:
            pass
    except Exception:
        log.exception("Command failed: %s", cmd)
        try:
            ui_log.write_line("✗ Error — see log.")
        except Exception:
            pass
```

---

## Group 2 — Worker-after-dismiss in LocalAI / SDForge / Vault screens (C2)

These screens use their own `query_one` calls outside of `_run_cmd`, so Group 1 doesn't cover them.

### `modules/localai/project_screen.py` — `_run_inference`
Wrap the initial `query_one("#output-log")` in `try/except Exception: return` and wrap each
subsequent `ui_log.write_line(...)` call inside the streaming loop in `try/except Exception: break`.

### `modules/sdforge/project_screen.py` — `_set_model`, `_generate`
- `_set_model` (lines ~91–112): wrap all four `query_one(...)` calls in `try/except Exception`.
- `_generate` (~lines 421–477): wrap the initial `query_one` at the top; wrap each subsequent
  UI write in the streaming loop in `try/except Exception: break`.

### `modules/localai/model_browser_screen.py` — `_fetch_installed`, `_pull_model`
Both call `query_one("#pull-log")` then write to it across async work. Wrap initial `query_one`
with `try/except Exception: return`; wrap each `write_line` in the streaming loop with
`try/except Exception: break`.

### `modules/vault/project_screen.py` — `_kp_list`
Line 277: `query_one("#output-log")` with no guard. Wrap with `try/except Exception: return`.

---

## Group 3 — Remaining `assert proc.stdout` instances (C3)

**`nexus/core/docker_ops.py:39`** — `pull_image` uses `assert proc.stdout`. Replace with:
```python
if proc.stdout is None:
    raise DockerError("docker pull: stdout unavailable")
```

**`modules/localai/model_browser_screen.py:153`** — `_pull_model` uses `assert proc.stdout`.
Replace with:
```python
if proc.stdout is None:
    pull_log.write_line("✗ ollama pull: stdout unavailable")
    return
```
Also wrap `await proc.wait()` in a `try/finally` to ensure the process is always awaited even
if an exception occurs during streaming.

---

## Group 4 — Vault path traversal (C4)

**File:** `modules/vault/project_screen.py`

Three operations — `_encrypt_with_age` (line 239), `_decrypt_with_age` (line 300), `_gpg_import`
(line 265) — accept user-typed file paths with no containment check. A user can type
`../../../../etc/shadow` and the app passes it directly to `age`/`gpg`.

**Fix** — add a helper and call it at the top of each method:
```python
def _validate_file_in_vault(self, file_path: Path) -> bool:
    vault_dir = Path(self._mod.get("vault_dir", "")).expanduser().resolve()
    resolved  = file_path.resolve()
    if not str(resolved).startswith(str(vault_dir) + "/") and resolved != vault_dir:
        self.app.notify(
            "File must be inside the vault directory.", severity="error"
        )
        return False
    return True
```

Call `if not self._validate_file_in_vault(file_path): return` in each of the three methods,
after `expanduser()` and before any subprocess call.

---

## Group 5 — SDForge `launch_args` shell injection (C5)

**File:** `modules/sdforge/project_screen.py:316`

`cmd = f"bash webui.sh {launch_args}"` is passed to `create_subprocess_shell`. Any shell
metacharacter in `launch_args` (from user-editable `config.yaml`) executes arbitrary commands.

**Fix:**
```python
import shlex
parts = shlex.split(launch_args) if launch_args.strip() else []
self._proc = await asyncio.create_subprocess_exec(
    "bash", "webui.sh", *parts,
    cwd=str(install_dir),
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.STDOUT,
    env={**os.environ, "COMMANDLINE_ARGS": launch_args},
)
```

---

## Group 6 — Docker: daemon availability check (H3)

**File:** `nexus/core/docker_ops.py:12`

`is_available()` only checks `shutil.which("docker")`. If the daemon is stopped or the user
lacks socket permissions, every Docker operation fails with a cryptic error.

**Fix** — replace with an async check that actually pings the daemon:
```python
async def is_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "ps",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()
        return proc.returncode == 0
    except Exception:
        return False
```

Update all callers in `docker_screen.py` to `await docker_ops.is_available()`.

---

## Group 7 — Docker: verify container actually running after `docker run -d` (H2)

**File:** `nexus/core/docker_ops.py:75–83`

`docker run -d` returns exit code 0 even if the container's entrypoint crashes immediately.
The UI says "✓ Container started" while the container is already exited.

**Fix** — add a status poll after `run_container` succeeds in `docker_screen.py._start()`:
```python
await docker_ops.run_container(...)
# Brief poll to catch fast exit
import asyncio as _aio
await _aio.sleep(1.5)
status = await docker_ops.container_status(c.name)
if status not in ("running",):
    ui_log.write_line(f"⚠ Container exited immediately (status: {status}). Check logs.")
    self.app.notify("Container exited immediately — check Docker log.", severity="warning")
else:
    ui_log.write_line("✓ Container started.")
    self.app.notify(f"'{c.name}' started.", severity="information")
```

Also fix `stop_container` to not raise on "No such container" (idempotent stop):
```python
if proc.returncode != 0:
    msg = stderr.decode(errors="replace").strip()
    if "No such container" not in msg:
        raise DockerError(msg or f"docker stop failed (code {proc.returncode})")
```

---

## Group 8 — Docker: concurrent pull prevention (M1)

**File:** `nexus/ui/docker_screen.py:114`

Double-clicking "Pull Image" spawns two concurrent `docker pull` processes, potentially
corrupting the local image layer cache.

**Fix** — add `_pulling: bool = False` to `DockerManagerScreen` and guard `_pull`:
```python
async def _pull(self) -> None:
    if self._pulling:
        self.app.notify("Pull already in progress.", severity="warning")
        return
    self._pulling = True
    try:
        ...  # existing pull logic
    finally:
        self._pulling = False
```

---

## Group 9 — Docker: dangling containers on app force-quit (H1)

**File:** `nexus/app.py:44–46`, `nexus/ui/docker_screen.py`

When Nexus is force-killed (Ctrl+C, SIGKILL), running Docker containers are left alive,
holding ports. On next launch, `docker run -p` fails with "port already allocated".

**Fix** — track active containers on the app and stop them synchronously on unmount:

In `nexus/ui/docker_screen.py`:
```python
def on_mount(self) -> None:
    self.run_worker(self._refresh_status())
    self.app._docker_containers.add(self._config.name)  # register

def on_dismiss(self) -> None:
    self.app._docker_containers.discard(self._config.name)  # unregister
```

In `nexus/app.py`:
```python
_docker_containers: set[str] = set()

def on_unmount(self) -> None:
    if hasattr(self, "_scheduler"):
        self._scheduler.stop()
    # Best-effort stop of tracked containers
    import asyncio, subprocess
    for name in list(self._docker_containers):
        try:
            subprocess.run(["docker", "stop", "--time=5", name],
                           timeout=8, capture_output=True)
        except Exception:
            pass
```

Note: `on_unmount` is synchronous; we use stdlib `subprocess.run` (blocking) since asyncio
event loop may already be shutting down.

---

## Group 10 — `_installed` set race in model browser (H4)

**File:** `modules/localai/model_browser_screen.py:129` vs `103`

`_fetch_installed` writes `self._installed = {...}` while a concurrent `on_input_changed`
worker reads it in `_rebuild_catalog`. Models can flicker between installed/not-installed states.

**Fix** — snapshot the set before passing to `_rebuild_catalog`:
```python
# In _fetch_installed, replace:
await self._rebuild_catalog(model_catalog.search(query))
# With:
await self._rebuild_catalog(model_catalog.search(query), frozenset(self._installed))

# Update _rebuild_catalog signature:
async def _rebuild_catalog(self, models: list[dict], installed: frozenset | None = None) -> None:
    if installed is None:
        installed = frozenset(self._installed)
    ...
    ModelRow(m, installed=m["id"] in installed, ...)
```

Do the same in `on_input_changed`: snapshot before spawning the worker.

---

## Group 11 — `~/.ollama` volume mount not validated (H5)

**File:** `modules/localai/project_screen.py:198`

If `~/.ollama` doesn't exist, Docker creates it as root (wrong permissions). If it's a symlink,
Docker follows it and may expose unintended host directories inside the container.

**Fix** — validate/create before building `DockerContainerConfig`:
```python
def _open_docker(self) -> None:
    from pathlib import Path
    ollama_path = Path.home() / ".ollama"
    if ollama_path.is_symlink():
        self.app.notify("~/.ollama is a symlink — refusing to mount.", severity="error")
        return
    ollama_path.mkdir(parents=True, exist_ok=True)
    volumes = {str(ollama_path): "/root/.ollama"}
    ...
```

---

## Medium fixes (lower priority, same session)

### M2 — `_server_ready` flag race in SDForge
**File:** `modules/sdforge/project_screen.py:346`  
Replace `self._server_ready: bool` with `self._server_ready_event = asyncio.Event()`. Use
`event.set()` / `event.clear()` / `event.is_set()` at each access site. Eliminates the
read-write race between `_stream_server_output` and `_stop_server`.

### M5 — `_pubkey_from_age_key` missing `exists()` guard
**File:** `modules/vault/project_screen.py:231`  
Add `if not self._age_key_path.exists(): return ""` before the fallback `read_text()` call
to avoid a bare `FileNotFoundError` propagating up with a misleading message.

### M6 — `--gpus all` without nvidia-container-toolkit check
**File:** `modules/sdforge/project_screen.py:292`  
After `extra = ["--gpus", "all"]` is determined, check `shutil.which("nvidia-container-runtime")`.
If not found, warn the user: `"--gpus all was requested but nvidia-container-toolkit may not be
installed — start may fail."` Still attempt start; let Docker surface the exact error.

### M4 — `_on_before_save` allows invalid binary paths to persist
**Files:** `modules/streaming/project_screen.py:37`, `modules/emulator/project_screen.py:97`  
Change severity from `"warning"` to `"error"` and make the message clearer: `"Binary not found
— save blocked. Fix the path or install the tool."` Keep the save blocked (raise an exception or
return a sentinel). Check what `BaseProjectScreen._on_save` does with the return value and
wire accordingly.

---

## Files to modify

| File | Groups |
|------|--------|
| `nexus/ui/base_project_screen.py` | 1 |
| `modules/localai/project_screen.py` | 2, 11 |
| `modules/sdforge/project_screen.py` | 2, 5, M2, M6 |
| `modules/localai/model_browser_screen.py` | 2, 3, 10 |
| `modules/vault/project_screen.py` | 2, 4, M5 |
| `nexus/core/docker_ops.py` | 3, 6, 7 |
| `nexus/ui/docker_screen.py` | 7, 8, 9 |
| `nexus/app.py` | 9 |
| `modules/streaming/project_screen.py` | M4 |
| `modules/emulator/project_screen.py` | M4 |

---

## Verification

```bash
# Syntax check all changed files
python -m py_compile \
  nexus/ui/base_project_screen.py \
  nexus/core/docker_ops.py \
  nexus/ui/docker_screen.py \
  nexus/app.py \
  modules/localai/project_screen.py \
  modules/localai/model_browser_screen.py \
  modules/sdforge/project_screen.py \
  modules/vault/project_screen.py \
  modules/streaming/project_screen.py \
  modules/emulator/project_screen.py

# Import smoke tests
python -c "from nexus.ui.base_project_screen import BaseProjectScreen; print('base OK')"
python -c "from nexus.core.docker_ops import is_available, run_container; print('docker_ops OK')"
python -c "from nexus.ui.docker_screen import DockerManagerScreen; print('docker_screen OK')"
python -c "from modules.vault.project_screen import VaultProjectScreen; print('vault OK')"
python -c "from modules.sdforge.project_screen import SDForgeProjectScreen; print('sdforge OK')"

# shlex fix sanity check
python -c "
import shlex
assert shlex.split('--api --port 7860') == ['--api', '--port', '7860']
assert shlex.split('') == []
print('shlex OK')
"
```
