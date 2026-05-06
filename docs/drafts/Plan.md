# Plan — Session 06 May 2026

## Context

Five sets of changes requested for this session:

1. **Settings overhaul** — TUI gains individual tabs per system module; GUI gains a System Modules tab and per-capability model settings; both get renamed "Default Input Panel" selector and updated options.
2. **System module Integrated/Standalone modes** — system modules added to a project can either share the global settings (Integrated) or run as fully isolated instances with their own config (Standalone). Conflict detection for ports/resources.
3. **Calendar as a system module** — calendar infrastructure belongs globally; project-level "Integrated" calendar maps to the shared store; "Standalone" is a fully isolated instance. TUI gets a minimal month grid; GUI ports the `QCalendarWidget` + `EventDialog` from the operator codebase.
4. **AI settings expansion** — GUI Advanced section gets per-capability model selectors (matching TUI); both UIs get multi-provider API key support (Anthropic, OpenWebUI, OpenAI-compatible).
5. **WSL compatibility** — investigation complete; only two code-level fixes needed; rest is documentation.

---

## Current State (from codebase investigation)

### Settings

**TUI `settings_screen.py`** — 5 tabs:
- **General**: log level, "Default AI Panel" (`ai.default_panel`) with options `chat / local / claude_code / none`
- **Appearance**: theme selector
- **Setup**: dep checker/installer (per `_MODULE_DEPS` list including ollama, restic, docker, git, etc.)
- **System Modules**: LocalAI card (enable, endpoint, model) + Backup card (enable, backend, repo, password, paths, schedule)
- **AI Config**: provider buttons (login / api_key / local), Basic/Advanced toggle, per-capability model fields for: reasoning, coding, embedding, instruct, function_calling, vision, stt_tts

**GUI `settings_dialog.py`** — 5 tabs:
- **AI Config**: provider (api_key / local only, no "login"), Advanced section shows *parameter* overrides (max_tokens, temperature, context_window) — **no per-capability model selection**
- **Appearance**: theme + colour swatch
- **Setup**: dep checker/installer
- **MCP Servers**: full add/edit/remove (absent from TUI settings)
- **General**: default chat panel dropdown (Claude / Local AI / Shell)
- **No System Modules tab** — LocalAI, Backup, Git, Home, SDForge, Security, Server not configurable in GUI

### System Modules (from `module.toml` scan)
All 7 have `system = true`: `git`, `backup`, `home`, `sdforge`, `security`, `server`, `localai`

Of these, only `localai` and `backup` have settings cards in the TUI. `git`, `home`, `sdforge`, `security`, `server` have no settings representation at all.

Modules with setup screens: `git`, `backup`, `sdforge`, `localai`
Modules without: `home`, `security`, `server`

### Calendar
Currently `system = false` (feature module). Data: `projects/<slug>/data/calendar/events.json`. GUI already has `QTreeWidget` + `_AddEventDialog` with `QDateEdit`/`QTimeEdit`.

**Operator calendar** (`/home/constantin/operator/core/calendar_interface.py`):
- `CalendarInterface(QWidget)` using `QCalendarWidget` + `QListWidget` for selected-day events
- `EventDialog(QDialog)` with Title, Start Date (QDateEdit), Start Time (QTimeEdit), optional end time toggle, recurrence combo, Location, Description
- `CalDAVBridge` for bidirectional sync with Radicale (`http://localhost:5232/`)
- Library: PyQt6 (must adapt to PySide6)

### AI Client
Providers: `api_key` (Anthropic SDK) and `local` (OpenAI-compatible via httpx). Config keys: `ai.provider`, `ai.api_key`, `ai.local_endpoint`, `ai.local_model`. No multi-provider schema exists yet.

### WSL
`nexus/core/platform.py` already handles WSL fully:
- `_is_wsl()` reads `/proc/version` for "microsoft"
- `open_path()` tries `wslview` then `explorer.exe` when WSL is detected
- All path handling uses `Path.expanduser()`

Two gaps: PTY ioctl calls lack WSL 1 guards; GUI on WSL requires X11/Wayland setup (out of scope for code, needs documentation).

---

## Part 1: Settings Screen Overhaul

### 1a. TUI Settings — Tab Restructure

**Target tab order:** General · Appearance · Setup · Git · Backup · Calendar · AI Config · MCP · SDForge · Security · Server

**Remove:** "System Modules" tab (split into individual tabs).

**File:** `nexus/ui/tui/settings_screen.py`

**New tabs to add:**

| Tab | Config key prefix | Fields |
|-----|-------------------|--------|
| **Git** | `git` | User name, email, default remote (https/ssh radio), personal access token (masked), SSH key path |
| **Backup** | `system_modules.backup` | Move existing Backup card contents here |
| **Calendar** | `calendar` | Global calendar data path, CalDAV enable toggle, CalDAV endpoint, username, password, "Sync Now" button |
| **MCP** | `mcp` | Stub panel: "Configure MCP servers in the GUI (nexus --gui)" |
| **SDForge** | `sdforge` | Endpoint URL, API key (masked), "Test Connection" button |
| **Security** | `security` | Placeholder label: "Security module settings — standalone setup required" |
| **Server** | `server` | Apache/nginx config dir path, HTTP port, HTTPS port, web root, "Check Status" button |

**Modify General tab:**
- Rename "Default AI Panel" label → **"Default Input Panel"**
- Change `_panel_opts` from `[("Chat (built-in)", "chat"), ("Local AI", "local"), ("Claude Code Cli", "claude_code"), ("None", "none")]` to `[("Local AI", "local"), ("Claude Code CLI", "claude_code"), ("Shell", "shell")]`
- Config key stays `ai.default_panel`; add `"shell"` as a valid value

**Modify AI Config tab (Local section):**
- Add an "Ollama Setup →" button positioned bottom-right of the Local AI card (same row as existing Save/Close area, right-aligned)
- On click: run `shutil.which("ollama")`
  - Found → `app.notify("Ollama is already installed.")`, done
  - Not found → push `_OllamaSetupModal(ModalScreen)` (see §1c)

**Move LocalAI card to System Modules tab → new Backup tab content only:**  
The existing System Modules tab is retired; its LocalAI card moves to "AI Config" tab (it already lives there) and its Backup card content moves into the new "Backup" tab.

### 1b. GUI Settings — Parity Fixes

**File:** `nexus/ui/gui/settings_dialog.py`

**Add "System Modules" tab** (new `_SystemModulesTab(QWidget)`) placed between Setup and General tabs.

Contents: a `QScrollArea` with cards (one per system module group) using `QGroupBox`:
- **Git card**: Username `QLineEdit`, Email `QLineEdit`, Token `QLineEdit` (masked), Default Remote `QComboBox` (https/ssh), SSH Key Path `QLineEdit`
- **LocalAI card**: Enable `QCheckBox`, Endpoint `QLineEdit`, Model `QLineEdit`, "Test" button (reuse `_TestLocalWorker`)
- **Backup card**: Enable `QCheckBox`, Backend `QComboBox` (restic/rsync), Repo Path `QLineEdit`, Password `QLineEdit` (masked), Schedule `QComboBox`
- **Home card**: HA URL `QLineEdit`, Token `QLineEdit` (masked), "Test" button
- **SDForge card**: Endpoint `QLineEdit`, API Key `QLineEdit` (masked)
- **Server card**: Web root path `QLineEdit`, HTTP port `QSpinBox`, HTTPS port `QSpinBox`
- **Security card**: placeholder label

**Modify `_AITab` Advanced section:**  
Currently shows: model override, max_tokens, temperature, context_window.  
Add below those parameters: a "Per-capability Models" collapsible group with one row per capability — matching TUI's `_CAPABILITIES` list: reasoning, coding, embedding, instruct, function_calling, vision, stt_tts.  
Each row: capability label + enabled `QCheckBox` + model `QLineEdit`.  
Config key: `ai.models.<capability>.enabled` + `ai.models.<capability>.model` (already in `_DEFAULT_CONFIG`).

**Modify `_GeneralTab`:**  
Default chat panel options should match TUI update: `[("Local AI", "local"), ("Claude Code CLI", "claude_code"), ("Shell", "shell")]`. Remove "Claude (built-in)" option.

### 1c. Ollama Setup Modal (TUI)

**New class:** `_OllamaSetupModal(ModalScreen)` in `settings_screen.py`

Steps:
1. Detect architecture via `platform.machine()` — show detected arch
2. Show install command: `curl -fsSL https://ollama.com/install.sh | sh`
3. Two buttons: "Run Install" (pushes sudo confirmation via `SudoModal`, then runs) + "Cancel"
4. If "Run Install": run via `_run_cmd` pattern; stream output to a `Log` widget in the modal
5. On success: `app.notify("Ollama installed. Set the endpoint in AI Config → Local.")` + dismiss

Note: The `_DepSpec` for ollama already has `special="curl -fsSL https://ollama.com/install.sh | sh"` — reuse that install command string.

---

## Part 2: Integrated / Standalone Module Mode

### 2a. Architecture

When a system module is added to a project, it operates in one of two modes:

- **Integrated** (default): module reads connection details from the global settings (`config/settings.yaml`) but operates from the project directory for data files. Example: Git Integrated uses the global git username/token but clones into `project.path/repos/`.
- **Standalone**: module has its own config stored in the project's `config.yaml` under `modules_config.<id>`. Full independent instance. Port/resource conflict detection against global settings runs before saving.

**Config storage:** `projects/<slug>/config.yaml`
```yaml
modules_config:
  git:
    mode: "integrated"   # "integrated" | "standalone"
  localai:
    mode: "standalone"
    endpoint: "http://localhost:11435"
    model: "codellama"
```

**Files to modify:**

`nexus/core/config_manager.py`:
- Add `get_module_mode(cfg: dict, module_id: str) -> str` — returns `cfg.get("modules_config", {}).get(module_id, {}).get("mode", "integrated")`
- Add `get_system_module_global_config(module_id: str) -> dict` — reads `load_global_config()["system_modules"].get(module_id, {})` (or git/sdforge/server from dedicated global keys added in Part 1)
- Update `_DEFAULT_CONFIG` to include git, home, sdforge, server under `system_modules`

`nexus/core/project_manager.py`:
- Update `create_project()` — when adding a system module, write default `modules_config.<id>.mode = "integrated"` to config
- Update `setup_module()` — skip `auto_configure_module` for system modules in integrated mode (they read from global settings, no local config needed)

### 2b. Mode Selection UI

**TUI — `ModuleSelectorModal` in `project_hub_screen.py`:**
- When a system module toggle is turned On, push a `_ModeModeModal(ModalScreen)` showing:
  - Module name
  - Radio: "Integrated (uses global [module] settings)" / "Standalone (own isolated instance)"
  - Brief description of difference
  - OK / Cancel
- On OK: save mode choice, then call `setup_module` as before

**GUI — `_ProjectConfigDialog` in `project_hub_widget.py`:**
- When a system module is moved from Available → Active list, open a `_ModeModeDialog(QDialog)` with the same radio choice
- Store chosen mode in a temporary dict `_pending_modes: dict[str, str]`; write to config in `_open_config_dialog()` on Accept

### 2c. Per-Module Behavior

Modules check their mode in `project_screen.py` / `gui_screen.py` using:
```python
from nexus.core.config_manager import get_module_mode, get_system_module_global_config
mode = get_module_mode(self._project_cfg, "git")
if mode == "integrated":
    git_cfg = get_system_module_global_config("git")
else:
    git_cfg = self._project_cfg.get("modules_config", {}).get("git", {})
```

**Git:**
- Integrated: username/token/email from global `system_modules.git`
- Standalone: from `modules_config.git` in project config; own identity per project
- No conflict check needed (different repos)

**LocalAI:**
- Integrated: endpoint + model from `system_modules.localai`
- Standalone: endpoint + model from `modules_config.localai`; conflict check: if port matches global endpoint port, warn "This port is already used by the system LocalAI instance"

**Server:**
- Integrated: uses global Apache config from `system_modules.server`; project maps to a subdirectory of global web root
- Standalone: own port from `modules_config.server`; conflict check against global HTTP/HTTPS ports

**SDForge:**
- Integrated: endpoint from `system_modules.sdforge` (placeholder behaviour — no deep integration yet)
- Standalone: own endpoint from project config

**Home:**
- Integrated: HA URL + token from `system_modules.home`
- Standalone: own HA URL + token from project config

**Backup:**
- Integrated: uses global restic repo/password from `system_modules.backup`; backup paths include `project.path`
- Standalone: own repo path/password from project config

**Security:**
- Integrated: reads global security scan settings
- Standalone: isolated scan config (placeholder; full implementation deferred)

**Conflict Detection Helper** — new function `check_module_conflicts(module_id: str, project_config: dict) -> list[str]` in `config_manager.py`:
- Returns list of warning strings (empty = no conflicts)
- Checks: port overlap for localai/server, repo path overlap for backup

---

## Part 3: Calendar as a System Module

### 3a. Reclassify Calendar

**File:** `modules/calendar/module.toml`
- Change `system = false` → `system = true`
- This moves calendar from "Features" to "System Tools" in the project module selector

This affects: `add_project_screen.py` (TUI), `project_hub_screen.py` (module tile section), `project_hub_widget.py` (GUI icon bar), `_ProjectConfigDialog` available module list. All use `is_system_module()` already — the change in `.toml` propagates automatically.

### 3b. Data Layer: Global vs Project Calendar

**File:** `nexus/core/data/calendar.py`

Current: `CalendarData` hardcoded to `projects/<slug>/data/calendar/`

Changes:
- `CalendarData.__init__` accepts `data_dir: Path` parameter (no default — callers must specify)
- Add factory functions:
  ```python
  _GLOBAL_CAL_DIR = Path(__file__).parent.parent.parent.parent / "config" / "calendar"
  
  def get_global_calendar() -> CalendarData:
      _GLOBAL_CAL_DIR.mkdir(parents=True, exist_ok=True)
      return CalendarData(_GLOBAL_CAL_DIR)
  
  def get_project_calendar(slug: str) -> CalendarData:
      from nexus.core.project_manager import _PROJECTS_DIR
      d = _PROJECTS_DIR / slug / "data" / "calendar"
      d.mkdir(parents=True, exist_ok=True)
      return CalendarData(d)
  ```

**Mode-aware calendar access** in `project_screen.py` and `gui_screen.py`:
```python
mode = get_module_mode(cfg, "calendar")
if mode == "integrated":
    cal = get_global_calendar()
else:
    cal = get_project_calendar(self.project.slug)
```

Integrated mode additionally shows a read-only "Project Events" section from the project-local store (if it exists), merged below the global events.

**AI Skills** (`modules/calendar/skills.py`): update `_get_cal(slug)` helper to respect mode.

### 3c. TUI Calendar Screen — Month Grid

**File:** `modules/calendar/project_screen.py`

Replace the current minimal upcoming-events list with a two-section layout:

**Top section — Month grid** (fixed height ~7 rows):
```
     May 2026
Mo Tu We Th Fr Sa Su
             1  2  3
 4  5  6  7  8  9 10
11 12 13 14 15 16 17
18 19 20 21 22 23 24
25 26 27 28 29 30 31
```
- Days with events: highlighted via CSS class (e.g. bold text or colour)
- Selected day underlined/highlighted
- Navigation: "< Prev" and "Next >" buttons change the displayed month
- Click on a day number → filter the event list below to that day

**Bottom section — Event list** (scrollable):
- Shows upcoming 30 days by default; shows selected day's events when a day is clicked
- Each row: `[ID]  YYYY-MM-DD HH:MM  title [🔁 recurrence-type]`

**Action buttons:**
- `+ Add Event` → push `_AddEventModal` (replaces the current freeform text input with proper labeled fields: Title, Date `YYYY-MM-DD`, Time `HH:MM`, optional End, Recurrence combo, Description)
- `Edit Event` → push `_EditEventModal` pre-populated from selected event
- `Delete Event` → push `ConfirmModal`, then delete
- `< Prev Month` / `Next Month >` — month navigation (can be inline buttons in top bar)

### 3d. GUI Calendar Screen — Port from Operator

**File:** `modules/calendar/gui_screen.py`

Full rewrite porting from `/home/constantin/operator/core/calendar_interface.py` (adapting PyQt6 → PySide6, adjusting date format ISO-first, using project's CalendarData):

**Layout:**
```
┌──────────────────────────────────────────────────────────────────┐
│  [+ Add Event]  [Edit Selected]  [Delete Selected]  [Refresh]   │
├────────────────────┬─────────────────────────────────────────────┤
│  QCalendarWidget   │  Events for [selected date]:                │
│  (left pane,       │  QListWidget                               │
│   fixed width 300) │  - event items with title/time/recurrence  │
│                    │                                             │
└────────────────────┴─────────────────────────────────────────────┘
```

**`_EventDialog(QDialog)`** — port from operator's `EventDialog`:
- Title `QLineEdit`
- Date `QDateEdit` (default: selected day from calendar, format `yyyy-MM-dd`)
- Time `QTimeEdit` (format `HH:mm`)
- End Time checkbox + `QDateEdit` + `QTimeEdit` (show/hide on toggle)
- Recurrence `QComboBox`: None / Daily / Weekly / Monthly / Yearly
- Location `QLineEdit`
- Description `QTextEdit`
- OK / Cancel buttons

**Key differences from operator:**
- PySide6 not PyQt6 (Signal/slot syntax identical, just different imports)
- Date format: `yyyy-MM-dd` (ISO) not `dd.MM.yyyy` (German)
- Data source: `get_global_calendar()` or `get_project_calendar()` based on mode
- No CalDAV in this phase (deferred to later)

### 3e. Calendar Settings Tab

Already covered in §1a (Calendar tab in TUI) and §1b (System Modules tab in GUI with CalDAV fields). 

Global calendar data path default: `config/calendar/` (relative to nexus root). Configurable via settings so users can point it to a shared drive or existing calendar directory.

---

## Part 4: AI Settings Expansion

### 4a. Config Schema — Multi-Provider

**File:** `nexus/core/config_manager.py` — update `_DEFAULT_CONFIG["ai"]`

New schema (backwards compatible — old `api_key` and `local` provider values still work):
```yaml
ai:
  provider: "anthropic"   # "anthropic" | "openwebui" | "openai_compat" | "local"
  # Flat fields kept for backwards compat but deprecated:
  api_key: ""
  local_endpoint: "http://localhost:11434"
  local_model: ""
  # New nested per-provider config:
  providers:
    anthropic:
      api_key: ""            # falls back to ANTHROPIC_API_KEY env var
    openwebui:
      base_url: "http://localhost:3000"
      api_key: ""            # OpenWebUI-issued key (not Anthropic key)
    openai_compat:
      base_url: ""
      api_key: ""
      model: ""
    local:
      endpoint: "http://localhost:11434"
      model: ""
  model_mode: "basic"
  model: ""
  default_panel: "none"
  models:
    reasoning:        {enabled: true,  model: ""}
    coding:           {enabled: true,  model: ""}
    embedding:        {enabled: false, model: ""}
    instruct:         {enabled: true,  model: ""}
    function_calling: {enabled: true,  model: ""}
    vision:           {enabled: true,  model: ""}
    stt_tts:          {enabled: false, model: ""}
```

Migration: `load_global_config()` checks for old `provider: "api_key"` → rewrites to `"anthropic"`. Old flat `api_key` field is copied into `providers.anthropic.api_key` on first load.

**File:** `config/settings.example.yaml` — update to show new schema with comments.

### 4b. AIClient Refactor

**File:** `nexus/ai/client.py`

Current: reads `cfg["provider"]` and dispatches to `_chat_anthropic()` or `_chat_local()`.

Changes:
- Provider string `"api_key"` → `"anthropic"` (with backwards compat alias)
- New providers: `"openwebui"` and `"openai_compat"` both route to `_chat_local()` (they're OpenAI-compatible endpoints)
- Config resolution: read from `cfg["providers"][provider]` dict; fall back to old flat keys for backwards compat
- `_VerifyWorker`-equivalent async method `verify_connection()` → tests the current provider's endpoint:
  - `anthropic`: GET `https://api.anthropic.com/v1/models` with `x-api-key` header
  - `openwebui` / `openai_compat`: POST `/chat/completions` with `Authorization: Bearer <key>` (not Anthropic header)
  - `local`: existing `/chat/completions` test

For OpenWebUI specifically: OpenWebUI exposes the OpenAI-compatible API at `/api/` by default. The `base_url` should point to the OpenWebUI root (e.g. `http://localhost:3000`); the client appends `/api` as the effective endpoint for `/chat/completions` calls.

### 4c. TUI AI Config Tab Updates

**File:** `nexus/ui/tui/settings_screen.py`

- Add "OpenWebUI" and "OpenAI-compat" as provider buttons alongside the existing Login/API Key/Local
- When "OpenWebUI" selected: show Base URL field + API Key field
- When "OpenAI-compat" selected: show Base URL field + API Key field + Model field
- Provider button IDs: `btn-provider-anthropic`, `btn-provider-openwebui`, `btn-provider-openai-compat`, `btn-provider-local` (remove "login" unless Anthropic OAuth is implemented)
- Update save logic to write `providers.<id>` nested config

### 4d. GUI AI Config Tab Updates

**File:** `nexus/ui/gui/settings_dialog.py`, class `_AITab`

- Provider buttons: add "OpenWebUI" + "OpenAI-compat" to existing "API Key" (rename → "Anthropic") + "Local" row
- Show/hide provider-specific form sections (same pattern as existing API Key / Local sections)
- OpenWebUI section: Base URL + API Key + "Verify" button (tests `/api/chat/completions`)
- OpenAI-compat section: Base URL + API Key + Model + "Test" button

**Advanced section — per-capability models** (already covered in §1b):
- Add `QGroupBox("Per-capability Models")` at bottom of Advanced section
- One row per capability: `QLabel` + enabled `QCheckBox` + model `QLineEdit`

---

## Part 5: WSL Compatibility

### 5a. Code Fixes (2 items only)

**PTY ioctl guards:**

File `nexus/ui/tui/terminal_widget.py` (around ioctl call):
```python
try:
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
except OSError:
    pass  # WSL 1 or non-POSIX environment
```

File `nexus/ui/gui/pty_terminal.py` (around ioctl call):
```python
try:
    fcntl.ioctl(fd, termios.TIOCSWINSZ, ...)
except OSError:
    pass  # WSL 1 or non-POSIX environment
```

### 5b. WSL Detection Utility (expose publicly)

**File:** `nexus/core/platform.py`

`_is_wsl()` is currently private. Expose it as `is_wsl() -> bool` (public alias, no code change needed — just rename or add public wrapper).

Add `is_wsl_1() -> bool`:
```python
def is_wsl_1() -> bool:
    """WSL 1 has limited POSIX support — no full ioctl, no /proc/net, etc."""
    if not is_wsl():
        return False
    try:
        v = Path("/proc/version").read_text()
        # WSL 1 kernel versions typically < 5.x
        import re
        m = re.search(r"Linux version (\d+)\.", v)
        return bool(m and int(m.group(1)) < 5)
    except OSError:
        return False
```

Use `is_wsl_1()` guard in terminal_widget and pty_terminal for the ioctl call.

### 5c. GUI on WSL — Startup Check

**File:** `nexus/ui/gui/app.py`

Add at launch (before creating `QApplication`):
```python
from nexus.core.platform import is_wsl
if is_wsl() and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
    print(
        "Nexus GUI requires a display server.\n"
        "On WSL 2 (Windows 11): WSLg provides this automatically.\n"
        "On WSL 2 (Windows 10): install VcXsrv and set DISPLAY=:0\n"
        "On WSL 1: upgrade to WSL 2 for GUI support.\n"
    )
    sys.exit(1)
```

### 5d. Documentation

Add `docs/wsl.md` (brief, ~30 lines):
- WSL 2 required for GUI (WSL 1 TUI-only)
- Windows 11 WSLg: no extra setup
- Windows 10: VcXsrv setup steps
- Known limitation: `wslview` depends on `wslu` package (`sudo apt install wslu`)
- TUI works fully on WSL 1 and WSL 2

---

## Critical Files

| File | Change |
|------|--------|
| `nexus/ui/tui/settings_screen.py` | New tabs (Git, Backup, Calendar, MCP, SDForge, Security, Server); rename panel selector; Ollama Setup button; new provider buttons (OpenWebUI, OpenAI-compat) |
| `nexus/ui/gui/settings_dialog.py` | System Modules tab; per-capability models in Advanced; new provider buttons; update panel options |
| `nexus/core/config_manager.py` | Multi-provider schema; `get_module_mode()`; `get_system_module_global_config()`; `check_module_conflicts()`; updated `_DEFAULT_CONFIG` |
| `nexus/ai/client.py` | Multi-provider routing; OpenWebUI/OpenAI-compat support; provider config reads from `providers.<id>` |
| `nexus/core/data/calendar.py` | `data_dir` parameter; `get_global_calendar()`; `get_project_calendar()` factories |
| `modules/calendar/module.toml` | `system = true` |
| `modules/calendar/project_screen.py` | Month grid view; proper Add/Edit/Delete modals; mode-aware data access |
| `modules/calendar/gui_screen.py` | Full rewrite: `QCalendarWidget` + `_EventDialog` ported from operator |
| `modules/calendar/skills.py` | Mode-aware `_get_cal()` helper |
| `nexus/core/project_manager.py` | `create_project()` writes default `modules_config.<id>.mode` for system modules; `setup_module()` skips auto-config for integrated system modules |
| `nexus/ui/tui/project_hub_screen.py` | Mode selector modal when toggling system modules On |
| `nexus/ui/gui/project_hub_widget.py` | Mode selector dialog when adding system modules |
| `nexus/ui/tui/terminal_widget.py` | ioctl WSL 1 guard |
| `nexus/ui/gui/pty_terminal.py` | ioctl WSL 1 guard |
| `nexus/ui/gui/app.py` | WSL display check |
| `nexus/core/platform.py` | Public `is_wsl()` + `is_wsl_1()` |
| `config/settings.example.yaml` | Updated schema |

---

## Sequence

1. **Config schema** (`config_manager.py`) — all other parts read from here; do first
2. **AIClient multi-provider** (`ai/client.py`) — schema-dependent
3. **WSL fixes** (`terminal_widget.py`, `pty_terminal.py`, `platform.py`, `app.py`) — self-contained, do early
4. **TUI Settings overhaul** (`settings_screen.py`) — new tabs + rename + Ollama modal + new providers
5. **GUI Settings overhaul** (`settings_dialog.py`) — System Modules tab + per-capability + new providers
6. **Calendar data layer** (`nexus/core/data/calendar.py`) — before module screens
7. **Calendar system module** (`module.toml`, `project_screen.py`, `gui_screen.py`, `skills.py`)
8. **Integrated/Standalone architecture** (`config_manager.py` helpers + `project_manager.py`)
9. **Mode selection UI** (TUI `project_hub_screen.py` + GUI `project_hub_widget.py`)
10. **Update `settings.example.yaml`** — final

---

## Verification

- **Settings tabs (TUI):** `uv run nexus` → press `s` → confirm tabs: General, Appearance, Setup, Git, Backup, Calendar, AI Config, MCP, SDForge, Security, Server; confirm "Default Input Panel" label shows "Local AI / Claude Code CLI / Shell"; confirm Ollama Setup button appears in AI Config Local section
- **Settings tabs (GUI):** `uv run nexus --gui` → Settings → confirm System Modules tab exists with all cards; confirm Advanced AI section has per-capability model rows; confirm provider buttons include OpenWebUI
- **Multi-provider:** Configure OpenWebUI provider → send a message → confirm it routes to local endpoint with Bearer auth
- **Calendar reclassified:** Open project hub module selector in TUI → confirm calendar appears under "System Tools" not "Features"
- **Calendar integrated mode:** Add calendar (integrated) to project → open it → confirm events read from `config/calendar/events.json`, not project-local store
- **Calendar month grid (TUI):** Open calendar module → confirm month grid renders accurately with today highlighted; navigate months with Prev/Next; click a day → event list filters
- **Calendar GUI date picker:** Add event → confirm `_EventDialog` opens with `QDateEdit` not freeform text input; end time toggle works; recurrence combo present
- **Integrated/Standalone:** Add Git module → confirm mode dialog appears → choose Standalone → confirm project config has `modules_config.git.mode: standalone`; open Git module → confirm it reads project-local credentials, not global
- **Conflict detection:** Add LocalAI standalone with same port as global → confirm warning is shown before saving
- **WSL (if available):** Run `uv run nexus` in WSL 2 → TUI opens; ioctl errors do not crash; `uv run nexus --gui` without DISPLAY → clear error message shown

