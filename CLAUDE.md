# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

Nexus is a Python-based personal organiser with a tile-based Textual TUI and an optional PySide6 desktop GUI. It integrates AI (Claude API, local models via OpenAI-compatible endpoints) and connects to external tools via MCP servers. Each project type is a module; multiple instances of the same type are allowed.

**Design philosophy:** AI is a progressive enhancement — all core modules work without an API key. Never treat AI as a hard dependency.

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
    config_manager.py  — settings.yaml + per-project config.yaml; is_ai_configured()
    module_manager.py  — _REGISTRY, needs_setup(), get_setup_screen(), get_project_screen()
    mycelium.py        — inter-module event bus (singleton `bus`)
    platform.py        — open_path(), check_binary(), read_clipboard(), write_clipboard()
    project_manager.py — create_project(), list_projects(), delete_project()
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
    tui/               — Textual screens (tiles, settings, mcp, base_project_screen, add_project)
    gui/               — PySide6 app (app.py, tile_grid.py, chat_panel.py, theme.py, base_project_window.py)
  assets/icons/        — nexus.svg app icon
  scripts/
    install_desktop.py — generates ~/.local/share/applications/nexus.desktop
modules/
  <id>/
    project_screen.py  — TUI screen (BaseProjectScreen subclass)
    gui_screen.py      — PySide6 window (GuiScreen, optional)
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

`module_manager.py` is the single dispatch point. `_REGISTRY` maps module IDs to `ModuleInfo`. Three functions drive everything: `needs_setup()`, `get_setup_screen()`, `get_project_screen()`.

To add a module: add `ModuleInfo` to `_REGISTRY`, implement the three conditionals, create `modules/<id>/project_screen.py` subclassing `BaseProjectScreen` with:
`MODULE_KEY`, `MODULE_LABEL`, `SETUP_FIELDS`, `_compose_action_buttons()`, `_populate_content()`, `_handle_action()`.

**Dual-UI rule:** every new module and every feature change must be reflected in both the TUI (`project_screen.py`) and the GUI (`gui_screen.py`). New modules require a STUB-level `gui_screen.py` at minimum. See `.claude/rules/dual-ui.md` for the full protocol, change-type table, and coverage tracker.

## Project Instances

Each project lives at `projects/<slug>/`:

- `config.yaml` — module-specific config + MCP overrides
- `CLAUDE.md` — per-project AI instructions (copied from module template)
- Module-specific dirs: `repos/` (git), `outputs/` (localai), `data/` (operator), etc.

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
