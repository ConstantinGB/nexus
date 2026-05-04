# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

Nexus is a Python-based personal organiser with a tile-based Textual TUI and an optional PySide6 desktop GUI. It integrates AI (Claude API, local models via OpenAI-compatible endpoints) and connects to external tools via MCP servers.

**Design philosophy:** Projects are containers of work. Modules are opt-in tools — a project can activate any combination. AI is a progressive enhancement — all core modules work without an API key.

## Running the App

**Package manager:** [uv](https://docs.astral.sh/uv/)

```bash
uv sync            # install dependencies
uv run nexus       # Textual TUI (default)
uv run nexus --gui # PySide6 desktop GUI
uv run nexus install-desktop  # install taskbar launcher
```

**TUI keyboard shortcuts:** `q` quit · `s` settings · `m` MCP servers · `Escape` go back

## Directory Layout

```
nexus/
  app.py               — entry point (NexusApp TUI + --gui dispatch + skill registration)
  core/
    config_manager.py  — settings.yaml + per-project config.yaml; mcp_servers() helper
    module_manager.py  — TOML-driven registry; needs_setup(), get_project_screen()
    project_manager.py — create_project(name, modules), list_projects(), delete_project()
    data/
      calendar.py      — CalendarData (shared by calendar module)
      notes.py         — NotesData (shared by notes module)
      tasks.py         — TodoData (shared by tasks module)
    mycelium.py        — inter-module event bus (singleton `bus`)
    platform.py        — open_path(), check_binary(), read_clipboard(), write_clipboard()
    scheduler.py       — BackupScheduler (asyncio polling, daily/weekly restic)
    logger.py          — RotatingFileHandler → logs/nexus.log; get("name") for child loggers
  ai/
    client.py          — AIClient: _chat_anthropic() + _chat_local(); full tool-use loop
    skill_registry.py  — SkillRegistry singleton: register(), get_tools(scopes), call()
    mcp_client.py      — MCPClient: connects to MCP servers via stdio
    mcp_registry.py    — curated MCP server catalog
    global_skills.py   — list_projects, run_flow, search_logs
    flow_handlers.py   — five Mycelium cross-module flows; register_flow_handlers()
  ui/
    tui/
      project_hub_screen.py — project entry point: module grid + ModuleSelectorModal
      setup_form.py         — reusable SetupForm widget (used by hub + BaseProjectScreen)
      base_project_screen.py
      add_project_screen.py — multi-select feature + system module tiles
      tiles.py, settings_screen.py, mcp_screen.py, ...
    gui/
      project_hub_widget.py — project entry point: icon bar + QStackedWidget + input panel
      app.py, tile_grid.py, chat_panel.py, theme.py, base_project_window.py, module_base.py
  assets/icons/        — nexus.svg app icon
  scripts/
    install_desktop.py — generates ~/.local/share/applications/nexus.desktop
modules/
  <id>/
    module.toml        — metadata: id, label, description, tags, system (bool), prefix
    project_screen.py  — TUI screen (BaseProjectScreen subclass)
    gui_screen.py      — PySide6 widget (GuiScreen, optional)
    setup_screen.py    — setup wizard (if module needs configuration)
    skills.py          — skill registrations
    CLAUDE.template.md — per-project AI context (copied to projects/<slug>/CLAUDE.md)
projects/              — project instances (git-ignored except .gitkeep)
config/
  settings.yaml        — global config: AI provider + MCP servers (git-ignored)
  settings.example.yaml
docs/drafts/           — dev planning documents (not committed)
```

## Module System

Modules are discovered at startup by scanning `modules/*/module.toml`. `module_manager.py` builds `_REGISTRY` (list of `ModuleInfo`), `MODULE_PREFIX` (id → prefix), and `_META` (full toml per module).

Key helpers:

- `list_feature_modules()` — modules where `system = false`
- `list_system_modules()` — modules where `system = true` (git, backup, localai, sdforge, security, home, server)
- `is_system_module(id)` — bool check
- `get_project_screen(project)` → always returns `ProjectHubScreen(project)`
- `get_project_screen_for_module(project, module_id)` → loads `modules/<id>/project_screen.py`
- `needs_setup_for_module(project, module_id)` → checks `module.toml [setup].config_check`

To add a module: create `modules/<id>/module.toml` and `modules/<id>/project_screen.py` subclassing `BaseProjectScreen` with:
`MODULE_KEY`, `MODULE_LABEL`, `SETUP_FIELDS`, `_compose_action_buttons()`, `_populate_content()`, `_handle_action()`.

**Dual-UI rule:** every new module and every feature change must be reflected in both the TUI (`project_screen.py`) and the GUI (`gui_screen.py`). New modules require a STUB-level `gui_screen.py` at minimum. See `.claude/rules/dual-ui.md` for the full protocol, change-type table, and coverage tracker.

## Project Instances

Each project lives at `projects/<slug>/`:

- `config.yaml` — `modules: list[str]` (the active module set) + per-module config + MCP overrides
- `CLAUDE.md` — per-project AI instructions (copied from the first matching module template)
- Module data dirs created on project creation: `repos/` (git), `notes/` (research), `data/calendar/` (calendar), `data/notes/` (notes), `data/todo/` (tasks), etc.

`ProjectInfo.modules` is the canonical field. The `.module` property returns `modules[0]` for backward compat.

## Logging

`setup_logging()` once at startup. `get("some.name")` → `logging.getLogger("nexus.some.name")`. Log at appropriate levels; use `log.exception(...)` for tracebacks.

---

Detailed guidance loaded on demand from `.claude/rules/`:

- `dual-ui.md` — dual-UI protocol: change types, GUI coverage levels, checklists (active when editing `modules/**` or `nexus/ui/**`)
- `ui-tui.md` — Textual patterns, async workers, robustness guards (active when editing TUI files)
- `ui-gui.md` — PySide6 patterns, QThread bridge (active when editing GUI files)
- `ai.md` — AIClient, skill system, MCP, Mycelium (active when editing `nexus/ai/**`)
- `modules.md` — full module table, skill inventory (active when editing `modules/**`)
- `security.md` — security invariants, injection prevention (active when editing any code)
