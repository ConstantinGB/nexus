# Review — 2026-04-29

## Context

Multi-agent sweep of the Nexus codebase (5 parallel agents).
**47 raw findings across 28 files; 38 retained after deduplication.**
Systemic issues: blocking I/O in async skills, unguarded `query_one` in workers,
path traversal in skill file-write operations, missing `event.stop()` in modal handlers.

---

## P1 — Bugs / Security

### Path traversal / containment bypasses (3 findings)

**`modules/vault/skills.py:97`** — `vault_encrypt_file` skill joins the `path` arg directly
to vault operations without calling `_validate_file_in_vault()`. The UI (`project_screen.py`
lines ~255–345) does call the validator, but the AI-invocable skill does not. An AI or
crafted tool-call can encrypt/read files outside the configured vault directory.
*Flagged by Agent E.*

**`modules/research/skills.py:61–77`** — `filename` from `args["filename"]` is joined to
`notes_dir` (`Path(notes_dir) / filename`) with no `Path.resolve()` containment check.
Input `"../../../etc/cron.d/nexus"` writes outside the notes directory.
*Flagged by Agent C.*

**`modules/emulator/skills.py:70–73`** — `rom` arg from `args["rom"]` is used to construct
a path via `content_dir / rom` with no check that the resolved path stays within `rom_dir`.
A crafted value like `"../../.ssh/id_rsa"` can open files outside the ROM library.
*Flagged by Agent E.*

### Crash on malformed remote-endpoint response

**`nexus/ai/client.py:136`** — `r.json()["choices"][0]` — no bounds check, no try/except.
A local endpoint that returns `{"choices": []}` (empty list) or omits `"choices"` entirely
raises `IndexError` / `KeyError`, crashing the entire chat loop.
*Flagged by Agent A.*

---

## P2 — Broken behaviour

### SYSTEMIC: Blocking I/O in async skill handlers (11 instances)

Skills are called from the asyncio AI-response loop. Synchronous file reads/writes in skill
handlers block the event loop, freezing the UI until the call returns. All instances below
need wrapping in `await asyncio.to_thread(...)`.

| File | Line(s) | Operation |
| ---- | ------- | --------- |
| `modules/vault/skills.py` | 31 | `.read_text()` in `_get_age_pubkey()` |
| `modules/web/skills.py` | 31 | `.read_text()` on `package.json` |
| `modules/custom/skills.py` | 72 | `.read_text()` on `CLAUDE.md` |
| `modules/codex/skills.py` | 35 | `.read_text()` loop over all notes |
| `modules/codex/skills.py` | 93 | `.write_text()` in `_codex_new_entry()` |
| `modules/research/skills.py` | 34 | `.read_text()` loop in `_research_list_notes()` |
| `modules/research/skills.py` | 73 | `.write_text()` in `_research_new_note()` |
| `modules/journal/skills.py` | 92 | `.write_text()` in `_journal_new_entry()` |
| `modules/org/skills.py` | 87, 128, 169 | `.write_text()` in all three org create skills |
| `modules/security/skills.py` | 151 | `.read_text()` on `/etc/resolv.conf` |
| `modules/streaming/skills.py` | 101 | `.stat()` call outside executor |

### SYSTEMIC: Blocking I/O in UI event handlers (not wrapped in run_worker)

These calls run on the Textual event-loop thread and freeze the UI:

| File | Line(s) | Description |
| ---- | ------- | ----------- |
| `modules/journal/project_screen.py` | 134 | `.stat()` calls via `sorted()` in `_handle_action` |
| `modules/journal/project_screen.py` | 142–150 | `.mkdir()` + `.write_text()` in `_create_entry()`, called directly |
| `modules/journal/project_screen.py` | 175–180 | `rglob()` + `.stat()` in `_compile_latest()`, called directly |
| `modules/org/project_screen.py` | 156 | `_create_file()` (`.write_text()`) called from `_handle_action` |
| `modules/streaming/project_screen.py` | 145, 151 | `.stat()` + `.read_text()` in `_handle_action` |
| `modules/game/project_screen.py` | 25 | `.read_text()` on `project.godot` in `_on_before_save` |
| `modules/home/project_screen.py` | 34 | `.is_dir()` in `_on_before_save` |
| `modules/vtube/project_screen.py` | 53 | `.exists()` in `_on_before_save` |

### SYSTEMIC: Unguarded `query_one` in async workers (9 instances)

Workers continue after a screen is dismissed. Any `query_one` that runs after dismissal
raises `NoMatches`. These are not wrapped in `try/except`:

| File | Line(s) | Context |
| ---- | ------- | ------- |
| `nexus/ui/chat_panel.py` | 134, 139, 153 | `_send()` worker: `#chat-input`, `#chat-log`, `#chat-send` |
| `nexus/ui/chat_panel.py` | 200 | `_do_init()` worker: `#chat-log` |
| `nexus/ui/base_project_screen.py` | 565, 577 | `_launch_claude()` / `_launch_bash()`: `#terminal-panel` after `_set_panel_mode` |
| `modules/git/project_screen.py` | 66 | `CommitModal._load_status()`: `#cm-diff-log` |
| `modules/git/project_screen.py` | 148 | `BranchModal._load_branches()`: `#br-list` |
| `modules/git/project_screen.py` | 282, 287 | `StashModal._load_stashes()`: `#st-list`, `#btn-st-pop` |
| `modules/vault/project_screen.py` | 127 | `#output-log` query |

### SYSTEMIC: Missing `event.stop()` in button handlers (3 instances)

Button presses bubble to parent containers and trigger duplicate handlers:

| File | Line | Context |
| ---- | ---- | ------- |
| `nexus/ui/tiles.py` | 76 | `ConfirmDeleteModal.on_button_pressed` |
| `nexus/ui/mcp_screen.py` | 83–95 | `ServerConfigForm.on_button_pressed` |
| `nexus/ui/add_project_screen.py` | 150–154 | `on_button_pressed` |

### One-off P2 findings

**`nexus/ai/flow_handlers.py:245–251`** — `entry_path = max(..., default=None)` can return
`None`; `entry_path.read_text()` at line ~256 is guarded by `if not entry_path` but the
None check is easy to miss if code is extended. Same pattern at lines 288–293 for
`plan_path`. Both are guard-by-proximity fragilities.

**`nexus/ai/mcp_client.py:28–30`** — `connect_all()` swallows individual server failures
silently. Partial connection leaves the tool set incomplete with no notification to the
caller or user. Caller cannot distinguish "connected to 0 servers" from "connected to N-1".

**`nexus/ui/mcp_screen.py:95`** — `self.app.query_one(MCPScreen).refresh_active()` is
called after `self.remove()` in `ServerConfigForm`. If `MCPScreen` was dismissed before
this runs, raises `NoMatches`.

**`nexus/ui/base_project_screen.py:476`** — `call_after_refresh(lambda: self.run_worker(self._launch_claude()))` and the equivalent bash lambda can fire after the screen is
dismissed. `_set_panel_mode` and `_launch_*` both call `query_one` internally — these
should guard against dismissal or cancel the deferred call on `action_dismiss`.

**`nexus/core/project_manager.py:56`** — `except Exception: continue` silently skips
projects with a corrupt `config.yaml`. Projects disappear from the tile grid with no
log message and no user notification.

**`nexus/app.py:49–57`** — `subprocess.run(["docker", "stop", ...])` is called directly
in `on_unmount()` (synchronous, main thread). With `timeout=8` and multiple containers
this can block for up to `8 × N` seconds on app exit. Acceptable in most cases but
notable on slow systems.

**`nexus/ai/client.py:131`** — Only `httpx.HTTPStatusError` with `status_code == 400`
is specially handled. `httpx.ConnectError`, `httpx.ReadTimeout`, and 5xx responses
bubble uncaught, surfacing raw stack traces in the chat log.

**`nexus/core/scheduler.py:48`** — `asyncio.CancelledError` in `_loop()` is caught by
`except Exception`, logs it as a generic error, and re-enters the loop rather than
stopping cleanly.

---

## P3 — Inconsistencies / Missing coverage

**`nexus/ai/client.py:37`** — `AsyncAnthropic(api_key="")` is created without validating
the key is non-empty; fails on first call rather than at init. A `Verify` button exists
in Settings but the client constructor is permissive.

**`nexus/ai/flow_handlers.py:66–81`** — LaTeX journal template uses `%` string formatting
with user-supplied `content`. If content contains `%` characters, the format call raises
`TypeError`. Should use `str.replace` or a safer template approach.

**`nexus/ai/mcp_client.py:72`** — `_tool_index` is built once at `connect_all()` and never
refreshed. If an MCP server crashes after startup, stale tool entries remain and calls
silently fail with no reconnect attempt.

**`nexus/ui/settings_screen.py:692, 705`** — `call_after_refresh(lambda: self._update_sections(...))` and `call_after_refresh(self._update_model_section)` mutate widget state inside a post-refresh callback. Per project convention, `call_after_refresh` should only trigger display refreshes, not state changes that other widgets might read between the frame and the callback.

**`modules/localai/project_screen.py:447`** — `create_subprocess_shell` used for inference
command with no `timeout` parameter. A hung inference process holds the panel indefinitely.

---

## Systemic patterns (root causes)

| Pattern | Count | Root cause |
| ------- | ----- | ---------- |
| Blocking I/O in skills | 11 | Skills were written as simple async fns; `asyncio.to_thread` not applied systematically |
| Blocking I/O in UI handlers | 8 | `_handle_action` is a sync dispatcher; file ops added inline rather than via `run_worker` |
| Unguarded `query_one` in workers | 9 | Worker-after-dismiss guard applied inconsistently; `_run_cmd` uses the pattern but direct `query_one` calls do not |
| Missing `event.stop()` | 3 | Button handler convention applied in some screens but not all modals |
| Path traversal in skills | 3 | Skills bypass the containment validators that the UI screens call |
