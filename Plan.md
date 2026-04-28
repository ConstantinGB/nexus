# Claude Code Panel — Implementation Plan

## Context

Replace the single "💬 AI" toggle with a two-button AI panel selector on every project
screen. Users can open either the existing in-app chat panel or a full Claude Code
terminal session (`claude` CLI via `app.suspend()`). A setting controls which mode
is active by default when any project is opened.

---

## 1 — How `app.suspend()` works

`App.suspend()` is a Textual built-in (synchronous context manager). It:

1. Pauses Textual's event loop and restores the raw terminal.
2. Runs the block inside — blocking is fine here, the TUI is paused.
3. Resumes Textual when the block exits (i.e. when the user `/exit`s claude).

```python
import subprocess, shutil
with self.app.suspend():
    subprocess.run(["claude"], cwd=str(self.project.path))
```

No new dependencies. Works from any synchronous event handler.

---

## 2 — Settings — add `ai.default_panel`

### `nexus/core/config_manager.py`

Add `"default_panel": "chat"` inside `_DEFAULT_CONFIG["ai"]`:

```python
"ai": {
    ...
    "default_panel": "chat",   # "chat" | "claude_code" | "none"
},
```

### `nexus/ui/settings_screen.py`

**In `compose()`**, replace the General tab's static rows with a live one for panel
default. Add below the existing readonly rows in `tab_general`:

```python
yield Label("Default AI panel:", classes="general-label")
with Horizontal(classes="general-row"):
    yield Label("Default AI panel", classes="general-label")
    yield Select(
        [("Chat (built-in)", "chat"),
         ("Claude Code CLI", "claude_code"),
         ("None", "none")],
        value=self._cfg.get("ai", {}).get("default_panel", "chat"),
        id="select-default-panel",
        allow_blank=False,
    )
```

**In `_save()`**, persist the value alongside the other AI settings:

```python
cfg["ai"]["default_panel"] = str(
    self.query_one("#select-default-panel", Select).value
)
```

---

## 3 — `nexus/ui/base_project_screen.py`

### 3a — Replace the single AI button with a paired group

Current top-bar compose (inside `compose()`):

```python
yield Button("💬 AI", id="btn-toggle-chat")
```

Replace with:

```python
yield Button("💬 Chat",   id="btn-panel-chat",   classes="panel-btn")
yield Button("⌨ Claude",  id="btn-panel-claude",  classes="panel-btn")
```

### 3b — CSS additions to `DEFAULT_CSS`

Replace the existing `#btn-toggle-chat` rule and add:

```css
.panel-btn          { margin-left: 1; }
.panel-btn-active   { border: solid #00FF88; color: #00FF88; }
```

Remove old rule: `#btn-toggle-chat { ... }` if it exists (it doesn't have one in the
current CSS so no removal needed — `margin-left: 1` is the only required addition).

### 3c — State tracking

Add instance attribute in `__init__`:

```python
self._panel_mode: str = "none"   # "none" | "chat" | "claude_code"
```

### 3d — `on_mount` — apply default

```python
def on_mount(self) -> None:
    ...  # existing lines unchanged
    self.call_after_refresh(self._apply_panel_default)
```

```python
def _apply_panel_default(self) -> None:
    from nexus.core.config_manager import load_global_config
    default = load_global_config().get("ai", {}).get("default_panel", "chat")
    if default == "chat":
        self._set_panel_mode("chat")
    elif default == "claude_code":
        self._set_panel_mode("claude_code")
    # "none" → leave both inactive (chat already hidden by _hide_chat_initial)
```

### 3e — `_set_panel_mode(mode)` helper

Centralises all mode transitions:

```python
def _set_panel_mode(self, mode: str) -> None:
    self._panel_mode = mode
    # Chat panel visibility
    try:
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.display = (mode == "chat")
    except NoMatches:
        pass
    # Button highlight
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

### 3f — Button handler additions

Inside `on_button_pressed`, add alongside the existing elif chain:

```python
elif bid == "btn-panel-chat":
    # toggle: if already active, close it
    new_mode = "none" if self._panel_mode == "chat" else "chat"
    self._set_panel_mode(new_mode)

elif bid == "btn-panel-claude":
    if self._panel_mode == "claude_code":
        # already "active" — treat second click as launch
        self._launch_claude()
    else:
        self._set_panel_mode("claude_code")
        # immediately launch on first click too
        self._launch_claude()
```

> **UX rationale:** Chat toggles open/close. Claude launches immediately on every
> click (there's nothing to "show" in the pane — the full terminal takes over).
> The highlight on the Claude button is a persistent reminder of which mode is
> preferred / was last used.

### 3g — `_launch_claude()` method

```python
def _launch_claude(self) -> None:
    import shutil, subprocess
    if not shutil.which("claude"):
        self.app.notify(
            "'claude' not found on PATH — install Claude Code first.",
            severity="error",
        )
        return
    project_dir = str(self.project.path)
    with self.app.suspend():
        subprocess.run(["claude"], cwd=project_dir)
```

### 3h — Remove old `_toggle_chat` method and `btn-toggle-chat` handler

Delete the `_toggle_chat` method and its `elif bid == "btn-toggle-chat"` branch.
The `_set_panel_mode("chat")` / `_set_panel_mode("none")` path replaces it entirely.
`_hide_chat_initial` can stay as-is (it hides the panel at startup regardless).

---

## 4 — Verification

```bash
python -m py_compile nexus/core/config_manager.py
python -m py_compile nexus/ui/base_project_screen.py
python -m py_compile nexus/ui/settings_screen.py
uv run nexus
```

Manual checks:

- Open any project — two buttons appear: **💬 Chat** and **⌨ Claude**.
- Default is Chat: chat panel opens automatically, Chat button highlighted green.
- Click **💬 Chat** again → panel closes, button un-highlights.
- Click **⌨ Claude** → Nexus suspends, `claude` opens in the project directory,
  CLAUDE.md is picked up automatically. Exit claude → Nexus resumes cleanly.
- Settings → General → change "Default AI panel" to **Claude Code CLI** → Save.
- Open a project → no chat panel, Claude button highlighted; click it → claude launches.
- Settings → change default to **None** → no panel and no highlight on open.
- If `claude` is not on PATH → error notify, no crash.
