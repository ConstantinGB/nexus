# Claude Code Panel — In-App Terminal (Revised Plan)

## Context

Replace the `app.suspend()` approach with an embedded PTY terminal that runs `claude`
inside the Textual layout as a panel, side-by-side with the existing chat panel.
The two-button top-bar and settings key (`ai.default_panel`) remain unchanged.

---

## 1 — New dependency: `textual-terminal`

`textual-terminal` provides a `Terminal` widget backed by a pseudo-terminal (PTY).
It handles ANSI rendering, keyboard input forwarding, and process lifecycle.

```bash
uv add textual-terminal
```

This adds one line to `pyproject.toml` dependencies. No other changes outside
`base_project_screen.py`.

---

## 2 — Settings (unchanged)

`ai.default_panel` in `config_manager.py`, the `Select` widget in `settings_screen.py`,
and the `_save()` persistence are already implemented and require no changes.

---

## 3 — `nexus/ui/base_project_screen.py`

### 3a — Add `#terminal-panel` container to the layout

In `compose()`, inside `#body-row`, add an empty `Vertical` after `#chat-panel`.
The `Terminal` widget will be mounted into it dynamically on first use.

```python
with Horizontal(id="body-row"):
    with Vertical(id="main-pane"):
        with Vertical(id="content-area"):
            ...
    yield ChatPanel(..., id="chat-panel")
    yield Vertical(id="terminal-panel")   # Terminal mounted here on demand
```

### 3b — CSS additions

Add alongside the existing `#chat-panel` rule:

```css
#terminal-panel {
    width: 1fr;
    height: 1fr;
    display: none;
}
```

No removal needed — `#chat-panel` keeps its existing rule untouched.

### 3c — State tracking (unchanged)

`self._panel_mode: str = "none"` already exists. No change needed.

### 3d — `_set_panel_mode()` — add terminal panel visibility

Extend the existing helper to also show/hide `#terminal-panel`:

```python
def _set_panel_mode(self, mode: str) -> None:
    self._panel_mode = mode
    try:
        self.query_one("#chat-panel", ChatPanel).display = (mode == "chat")
    except NoMatches:
        pass
    try:
        self.query_one("#terminal-panel").display = (mode == "claude_code")
    except NoMatches:
        pass
    for bid, active_mode in [("btn-panel-chat", "chat"), ("btn-panel-claude", "claude_code")]:
        try:
            btn = self.query_one(f"#{bid}", Button)
            if mode == active_mode:
                btn.add_class("panel-btn-active")
            else:
                btn.remove_class("panel-btn-active")
        except NoMatches:
            pass
```

### 3e — Button handler for `btn-panel-claude` (revised)

Replace the current `elif bid == "btn-panel-claude"` branch:

```python
elif bid == "btn-panel-claude":
    if self._panel_mode == "claude_code":
        # Second click hides the panel; process keeps running
        self._set_panel_mode("none")
    else:
        self._launch_claude()
```

> **UX rationale:** First click opens and starts (or resurfaces) the terminal.
> Second click hides the panel without killing the process — the session is still
> alive and reappears on the next click. The button stays highlighted whenever
> a live terminal session exists, regardless of whether the panel is visible.

The `btn-panel-chat` handler is unchanged (toggle open/close).

### 3f — `_launch_claude()` rework (async)

Replace the `app.suspend()` implementation with a PTY-backed in-app terminal.
The method is now `async` because `mount()` is a coroutine.

```python
async def _launch_claude(self) -> None:
    import shutil, shlex
    from textual_terminal import Terminal

    if not shutil.which("claude"):
        self.app.notify(
            "'claude' not found on PATH — install Claude Code first.",
            severity="error",
        )
        return

    # Show panel first (fast, synchronous path)
    self._set_panel_mode("claude_code")

    # If a terminal widget already exists the session is still alive — just show it
    try:
        self.query_one("#claude-terminal")
        return
    except NoMatches:
        pass

    # Mount a fresh terminal running claude in the project directory
    project_dir = shlex.quote(str(self.project.path))
    terminal = Terminal(
        command=f"bash -c 'cd {project_dir} && exec claude'",
        id="claude-terminal",
    )
    panel = self.query_one("#terminal-panel")
    await panel.mount(terminal)
    terminal.start()
```

Update the button handler call-site to use `self.run_worker`:

```python
elif bid == "btn-panel-claude":
    if self._panel_mode == "claude_code":
        self._set_panel_mode("none")
    else:
        self.run_worker(self._launch_claude())
```

### 3g — Handle process exit

When `claude` exits inside the terminal, remove the widget and reset state so the
next click starts a fresh session:

```python
def on_terminal_process_stopped(self, event) -> None:
    try:
        self.query_one("#claude-terminal").remove()
    except NoMatches:
        pass
    # Only reset the mode if we're still in claude_code; the user may have
    # already switched to chat or none before the process finished.
    if self._panel_mode == "claude_code":
        self._set_panel_mode("none")
```

> **Note:** `textual-terminal` posts `Terminal.ProcessStopped` on exit.
> Verify the exact message class name against the installed version and adjust
> the handler name accordingly (`on_terminal_process_stopped` follows Textual's
> snake_case message routing convention).

### 3h — `_apply_panel_default` — auto-launch when default is `claude_code`

The existing `_apply_panel_default` calls `_set_panel_mode("claude_code")` for
the `claude_code` default. Update it to also trigger the launch:

```python
def _apply_panel_default(self) -> None:
    from nexus.core.config_manager import load_global_config
    default = load_global_config().get("ai", {}).get("default_panel", "chat")
    if default == "chat":
        self._set_panel_mode("chat")
    elif default == "claude_code":
        self.run_worker(self._launch_claude())
    # "none" → leave both inactive
```

### 3i — Remove old `_launch_claude` sync implementation

Delete the old `app.suspend()` / `subprocess.run` body entirely and replace it
with the async version in §3f above.

---

## 4 — Verification

```bash
uv add textual-terminal
python -m py_compile nexus/ui/base_project_screen.py
uv run nexus
```

Manual checks:

- Open any project — two buttons appear: **💬 Chat** and **⌨ Claude**.
- Click **⌨ Claude** → terminal panel opens inline; `claude` starts in the project
  directory; CLAUDE.md is picked up automatically.
- Terminal is interactive — type commands, receive responses, scroll output.
- Click **⌨ Claude** again → panel hides; process keeps running.
- Click **⌨ Claude** once more → same session resurfaces.
- `/exit` inside claude → terminal widget removed, button un-highlights, next click
  starts a fresh session.
- Chat and Claude panels are mutually exclusive — opening one hides the other.
- Settings → General → change "Default AI panel" to **Claude Code CLI** → Save.
  Open a project → terminal auto-starts in the panel.
- Settings → change default to **None** → no panel on open.
- If `claude` is not on PATH → error notify, no crash, no empty panel shown.
