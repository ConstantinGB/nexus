# Adversarial Review — 2026-04-30

Five parallel agents swept the codebase (core, UI, AI/MCP, modules batch 1, modules batch 2).
Findings are grouped by severity. Fix each before the next session ends.

---

## CRITICAL

### C-1 — Custom module shell injection
**File:** `modules/custom/project_screen.py:362`
User-defined commands from `config.yaml` are passed directly to `asyncio.create_subprocess_shell()`.
Any command containing `;`, `|`, `&&`, `$()`, etc. executes as shell code.
**Fix:** Switch to `create_subprocess_exec()` with `shlex.split(cmd)`, same pattern as `BaseProjectScreen._run_cmd`.

### C-2 — Service name injection (server module)
**File:** `modules/server/project_screen.py:277-290`
Service names entered via `_AddServiceModal` are passed unsanitised to `docker` and `systemctl` subprocesses.
A name like `nginx; rm -rf /` in the subprocess list form would not cause shell execution, but names containing
Docker-special syntax (`--privileged`, volume flags) could be misinterpreted.
**Fix:** Validate service names at save time: `re.match(r'^[a-zA-Z0-9_.-]+$', name)`. Reject on failure.

### C-3 — GitHub token embedded in subprocess command line
**File:** `modules/git/git_ops.py:51-69`
`clone_repo()` builds `https://oauth2:{token}@github.com/...` and passes it to `subprocess.run()`.
On Linux, `/proc/<pid>/cmdline` exposes this to any process running as the same user.
The token also appears in any git error messages (which are logged).
**Fix:** Use git's credential helper via `GIT_ASKPASS` or pass credentials via `GIT_CREDENTIAL_HELPER` /
`GIT_CONFIG_*` env vars instead of URL-embedding. Never put the token in the URL string.

### C-4 — PowerShell clipboard injection (Windows)
**File:** `nexus/core/platform.py:91`
`f"Set-Clipboard -Value '{text}'"` interpolates user text directly into a PowerShell command string.
Clipboard content containing `'; Remove-Item -Recurse C:\Windows; '` executes as PowerShell.
**Fix:** Use `-EncodedCommand` with a Base64-encoded payload, or pipe the value through stdin.

### C-5 — Unbounded tool-use loop (Anthropic path)
**File:** `nexus/ai/client.py:67-97`
`while True:` in `_chat_anthropic` has no iteration cap. A prompt injection or misbehaving model
can loop indefinitely, burning API quota and memory.
**Fix:** Add `iterations = 0` counter, break with error notification after `MAX_ITERATIONS = 10`.

### C-6 — Unbounded tool-use loop (local model path)
**File:** `nexus/ai/client.py:116-169`
Same issue in `_chat_local`.
**Fix:** Same fix as C-5.

### C-7 — Unhandled exception in skill handler crashes chat session
**File:** `nexus/ai/skill_registry.py:54-58`
`registry.call()` does not catch exceptions from handlers. Any uncaught exception in a skill
propagates up through the AI loop and kills the chat for that session.
**Fix:** Wrap handler call: `try: return await entry["handler"](args) except Exception as exc: log.exception(...); return json.dumps({"error": str(exc)})`

### C-8 — SDForge server not stopped on tab switch
**File:** `nexus/app.py` (`switch_to_tab`)
`switch_to_tab` calls `self.pop_screen()` directly, bypassing `SDForgeProjectScreen.action_dismiss()`.
The SD Forge server process is left running orphaned and unmanageable.
**Fix:** Before `pop_screen()`, check `if hasattr(current_screen, '_proc')` and stop the process,
or refactor so `switch_to_tab` calls `action_dismiss` on the outgoing screen.

---

## HIGH

### H-1 — `yaml.dump` instead of `yaml.safe_dump`
**Files:** `nexus/core/config_manager.py:69`, `nexus/core/project_manager.py:93`
`yaml.dump()` uses Python-object serialization; `yaml.safe_load()` is already used for reads.
If tainted data ever enters the config dict, it could be serialised with `!!python/object` tags
and execute on the next load.
**Fix:** Replace both with `yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)`.

### H-2 — Journal LaTeX template injection
**File:** `modules/journal/project_screen.py:16-35, 149`
The `author` config field is interpolated directly into a LaTeX template with `.format()`.
Setting `author = "\\input{/etc/passwd}"` would execute arbitrary LaTeX, potentially reading
or writing files depending on the LaTeX installation's security settings.
**Fix:** Escape LaTeX special characters in all user-supplied fields before interpolation:
`\ → \textbackslash{}`, `{ → \{`, `} → \}`, `$ → \$`, `& → \&`, `% → \%`, `# → \#`, `_ → \_`.

### H-3 — MCP tool call exception not caught (Anthropic path)
**File:** `nexus/ai/client.py:79-82`
`await self._mcp.call_tool(...)` re-raises on failure (see `mcp_client.py:78-82`).
Uncaught, it crashes the tool-use loop and kills the chat session.
**Fix:** Wrap in `try/except Exception as exc` and return `{"error": str(exc)}` as `tool_result`.

### H-4 — MCP tool call exception not caught (local model path)
**File:** `nexus/ai/client.py:160-161`
Same issue as H-3 in the local model path.
**Fix:** Same.

### H-5 — JSON parse error crashes local model tool-use loop
**File:** `nexus/ai/client.py:157`
`json.loads(tc["function"]["arguments"])` raises `JSONDecodeError` if the local model returns
malformed arguments. Not caught; crashes the loop.
**Fix:** Wrap in `try/except json.JSONDecodeError` and skip or error the call.

### H-6 — `skill_registry.call()` exception not caught in local model path
**File:** `nexus/ai/client.py:159`
`await registry.call(name, args)` is not wrapped; any skill exception crashes the loop.
**Fix:** Same pattern as C-7.

### H-7 — KeyError on missing `action` in `run_flow`
**File:** `nexus/ai/global_skills.py:46`
`args["action"]` raises `KeyError` if the model calls `run_flow` without the required field.
**Fix:** `action = args.get("action"); if not action: return json.dumps({"error": "action is required"})`

### H-8 — LocalAI Docker `~/.ollama` symlink TOCTOU
**File:** `modules/localai/project_screen.py:343-346`
`is_symlink()` check followed by `mkdir()` — an attacker can replace the path with a symlink
between the two calls, causing Docker to mount a sensitive directory into the container.
**Fix:** Use `os.open` with `O_NOFOLLOW | O_DIRECTORY | O_CREAT` or validate the path after
creation: `stat = os.stat(path, follow_symlinks=False); if stat.st_mode & 0o120000: raise`.

### H-9 — Concurrent backup operations not serialised
**File:** `modules/backup/project_screen.py:179-203`
`_do_backup()` runs via `run_worker()` with no guard. Double-clicking "Run Backup" starts two
concurrent restic processes against the same repository, which can corrupt it.
**Fix:** Add a `_backup_running: bool` flag; return early if already set; clear in `finally`.

### H-10 — Backup restore target not validated
**File:** `modules/backup/project_screen.py:242-252`
The restore target path comes from free-text `InputModal`. No check prevents restoring to
`/etc` or other system directories.
**Fix:** Require the target to be within the user's home directory, or at minimum show a clear
confirmation dialog listing the exact target path before executing.

### H-11 — ChatPanel history not cleared on project switch (tab system)
**File:** `nexus/ui/chat_panel.py:53-100`
`ChatPanel` is created once per `BaseProjectScreen` instance. When tabs switch, panels are
hidden/shown without being recreated, so `_load_history()` is only called once. The user sees
the previous project's conversation.
**Fix:** On becoming visible for a new project, reload history. Implement a `reset(slug)` method
and call it from `switch_to_tab`.

### H-12 — `InputModal` missing `event.stop()`
**File:** `nexus/ui/base_project_screen.py:61-70`
`on_button_pressed` does not call `event.stop()`, allowing events to propagate to the parent
screen and trigger unintended handlers.
**Fix:** Add `event.stop()` as the first line.

### H-13 — `SettingsScreen` missing `event.stop()`
**File:** `nexus/ui/settings_screen.py:705`
Same issue as H-12.
**Fix:** Add `event.stop()` as the first line.

### H-14 — GitHub API token sent to non-HTTPS endpoints
**File:** `modules/git/github_api.py:9-44, 60-80`
No scheme check before sending the `Authorization: Bearer` header. A misconfiguration could
redirect requests to an HTTP endpoint, exposing the token.
**Fix:** Assert `url.startswith("https://")` before making requests.

---

## MEDIUM

### M-1 — Vault path containment uses string prefix match
**File:** `modules/vault/project_screen.py:220-232`
`str(resolved).startswith(str(vault_dir) + "/")` is fooled by a vault at `/home/user/vault`
when the target is `/home/user/vault-evil/file`. The `+` trick is brittle.
**Fix:** Use `resolved.is_relative_to(vault_dir)` (Python 3.9+) or `resolved.relative_to(vault_dir)` in a `try/except ValueError`.

### M-2 — GPG export filename not path-traversal safe
**File:** `modules/vault/project_screen.py:278-285`
Output filename is built from the GPG key ID by replacing `@` and spaces. A key ID like
`../../../etc/passwd` passes through and writes outside the vault.
**Fix:** Apply `_slugify()` to the key ID, or call `_validate_file_in_vault()` on the output path.

### M-3 — Restic password visible in process environment
**File:** `modules/backup/backup_ops.py:7-10`
`RESTIC_PASSWORD` is passed in the subprocess `env=` dict, making it readable from
`/proc/<pid>/environ` by other processes running as the same user.
**Fix:** Use restic's `--password-command` flag with a small script that reads from a 0600 file,
or use `--password-file` with a temp file that is deleted after the process exits.

### M-4 — LocalAI prompt visible in process environment
**File:** `modules/localai/project_screen.py:462-473`
`NEXUS_PROMPT` / `NEXUS_NEGATIVE_PROMPT` env vars are readable from `/proc/<pid>/environ`.
**Fix:** Pass prompt values via subprocess stdin instead of environment.

### M-5 — Scheduler read-modify-write race on `last_run`
**File:** `nexus/core/scheduler.py:98-99, 124-125`
Config is loaded, modified, and saved without a file lock. A concurrent write loses changes.
**Fix:** Use `fcntl.flock()` (Unix) or a `.lock` file with atomic rename around the entire
load → modify → save sequence.

### M-6 — `create_project` TOCTOU on directory creation
**File:** `nexus/core/project_manager.py:78-83`
`exists()` check + `mkdir()` is non-atomic. A symlink attack can redirect writes.
**Fix:** Use `mkdir(exist_ok=False)` and catch `FileExistsError`.

### M-7 — `update_project_meta` missing error handling
**File:** `nexus/core/project_manager.py:124-130`
No `try/except` around the file open/write. `FileNotFoundError` propagates uncaught.
**Fix:** Wrap in `try/except OSError` and log the failure.

### M-8 — `list_projects` silently drops corrupted projects
**File:** `nexus/core/project_manager.py:48-59`
A project with a bad `config.yaml` disappears from the list with no user notification.
**Fix:** Return an entry flagged as `corrupted=True` and show it in the tile grid with a warning icon.

### M-9 — Scheduler silently runs backup on corrupted timestamp
**File:** `nexus/core/scheduler.py:30`
`except ValueError: return True` means any unparseable `last_run_iso` triggers an immediate run.
**Fix:** Log at WARNING and return `False` (skip) rather than triggering a spurious backup.

### M-10 — Docker container cleanup silently ignores errors
**File:** `nexus/app.py:73-79`
`except Exception: pass` in `on_unmount` swallows failures, leaving containers running.
**Fix:** Replace with `except Exception as exc: log.warning("Failed to stop container %s: %s", name, exc)`.

### M-11 — MCP required env vars not validated before server launch
**File:** `nexus/ai/mcp_client.py:38`
Required env vars (e.g., `GITHUB_TOKEN`) are not checked before spawning the MCP server.
The server starts and silently fails when it tries to use the missing var.
**Fix:** Validate all `required_env` keys exist in `os.environ` before `connect_one()`.

### M-12 — Tool result not marked `is_error` for Anthropic API
**File:** `nexus/ai/client.py:86`
Failed tool calls return an error JSON string but the `tool_result` block lacks `"is_error": true`.
Claude may misinterpret an error as a successful result.
**Fix:** Parse the result string; if it's a `{"error": ...}` dict, set `"is_error": True` in the block.

### M-13 — API key potentially logged in Anthropic client error path
**File:** `nexus/ai/client.py:38`
If `AsyncAnthropic(api_key=key)` raises, the traceback includes the `key` variable.
**Fix:** Validate `if not key: raise ValueError("ANTHROPIC_API_KEY not configured")` before passing.

### M-14 — Race condition in chat panel message append
**File:** `nexus/ui/chat_panel.py:142, 184`
User message is appended immediately; if the AI call raises between append and pop (line 171),
the message list is left in an inconsistent state.
**Fix:** Use a single `try/finally` block: append at start, pop in `finally` on exception.

### M-15 — SDForge API no retry on HTTP 429 / 503
**File:** `modules/sdforge/api_client.py` (all async functions)
Rate-limit and service-unavailable responses fail immediately with no backoff.
**Fix:** Add retry with exponential backoff for status codes 429 and 503; respect `Retry-After` header.

### M-16 — Journal entry TOCTOU between `exists()` and `write_text()`
**File:** `modules/journal/project_screen.py:145-148`
Non-atomic check-then-write can overwrite a concurrently created file.
**Fix:** Use `open(entry_path, 'x')` (exclusive create) and catch `FileExistsError`.

### M-17 — Research async PDF export not cancelled on screen dismiss
**File:** `modules/research/project_screen.py:359-393`
If the screen is dismissed while pandoc is running, the coroutine is orphaned and may attempt
to update a destroyed widget, generating `NoMatches` exceptions.
**Fix:** Store the worker reference; cancel it in `action_dismiss()`.

### M-18 — `run_flow` payload type inconsistency
**File:** `nexus/ai/global_skills.py:48`
Schema declares `payload` as string, but a model returning a dict object causes `json.loads` to
receive a non-string, raising `TypeError`.
**Fix:** Accept both: `if isinstance(p, dict): payload = p else: payload = json.loads(p or "{}")`

### M-19 — `ConfirmDeleteModal` reused for non-deletion confirmations
**File:** `nexus/ui/tiles.py:68`, `nexus/ui/chat_panel.py:278`
The modal's title is hardcoded "Delete project?" but it's also used to confirm clearing chat history.
**Fix:** Make `title` a constructor parameter; pass appropriate text from each call site.

### M-20 — Logger `setup()` not thread-safe
**File:** `nexus/core/logger.py:18-19`
`if root.handlers:` double-initialization check races under concurrent calls.
**Fix:** Wrap with a `threading.Lock`.

---

## LOW

### L-1 — `action_next_tab` edge case when tab is closed mid-flight
**File:** `nexus/app.py:101-105`
`_active_tab_idx` can be stale if a tab closes between the key press and the handler.
**Fix:** Clamp: `next_idx = (self._active_tab_idx + 1) % max(len(self._tabs), 1)` with bounds check.

### L-2 — `auto_open_project` prefix ambiguity
**File:** `nexus/app.py:60`
Prefix-match `startswith(needle)` silently opens the first matching project if names collide.
**Fix:** Require exact match, or notify the user when multiple projects share the same prefix.

### L-3 — Empty AI reply appended to history
**File:** `nexus/ui/chat_panel.py:179`
`if reply is not None` passes when `reply == ""`, adding a blank message to history.
**Fix:** Change to `if reply is not None and reply.strip():`.

### L-4 — MCP tool index not synchronised on partial disconnect
**File:** `nexus/ai/mcp_client.py:92-93`
If `call_tool` is called after partial disconnection, `_tool_index` may reference a missing session.
**Fix:** Check session existence in `call_tool` before lookup.

### L-5 — Local model 400-error retry masks real failures
**File:** `nexus/ai/client.py:134`
A 400 from the local endpoint is assumed to mean "tools not supported"; other causes are silently retried.
**Fix:** Log the actual error body before retrying; only strip tools if the response body mentions tools.

### L-6 — AMD GPU detection truncated to 200 chars, NVIDIA untruncated
**File:** `modules/localai/hw_detect.py:48-66`
Inconsistent output length between GPU vendors.
**Fix:** Apply the same truncation limit to all vendors or remove the limit entirely.

### L-7 — `subprocess.Popen` without explicit `shell=False`
**Files:** `modules/sdforge/project_screen.py:403`, `modules/localai/project_screen.py:327`
Relies on the default; explicit is safer.
**Fix:** Add `shell=False` keyword argument.

### L-8 — `password=` field without explicit parentheses (mcp_screen)
**File:** `nexus/ui/mcp_screen.py:76`
`password="KEY" in env_key or ...` has ambiguous operator precedence (works today, fragile).
**Fix:** `password=("KEY" in env_key or "TOKEN" in env_key or "SECRET" in env_key)`.

### L-9 — Age key error message not specific enough
**File:** `modules/vault/project_screen.py:234-254`
Falls back to empty string with a generic notification; users can't diagnose why key extraction failed.
**Fix:** Surface which fallback path failed in the notification text.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 8     |
| HIGH     | 14    |
| MEDIUM   | 20    |
| LOW      | 9     |
| **Total**| **51**|

Priority for next session: C-1 (shell injection), C-3 (token in URL), C-5/C-6 (tool loops),
C-7 (skill crash), C-8 (SDForge orphan), H-2 (LaTeX injection), H-3/H-4/H-6 (MCP/skill crash paths).
