# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Nexus is a Python-based personalized organizational tool with a tile-based terminal UI for browsing and managing projects. It integrates AI/LLM support (Claude API, local models) and connects to external services via MCP servers. Each project type is a module; multiple instances of the same type are allowed.

**Design philosophy:** Nexus is designed to run independently of AI. All core modules work without an API key or local model; AI is an optional enhancement that improves output quality when available. Never assume AI is reachable — treat it as a progressive enhancement, not a hard dependency.

## Running the App

**Package manager:** [uv](https://docs.astral.sh/uv/)

```bash
uv sync          # install dependencies
uv run nexus     # run the app
```

**Keyboard shortcuts** (main screen):
- `q` — quit
- `s` — open Settings
- `m` — open MCP server manager
- `Escape` — go back from any screen

## Architecture

### Directory layout

```
nexus/
  app.py                 — NexusApp (Textual App), entry point
  core/
    config_manager.py    — read/write settings.yaml + per-project config.yaml; is_ai_configured() helper
    logger.py            — centralised logging (RotatingFileHandler → logs/nexus.log)
    module_manager.py    — module registry + screen dispatch
    mycelium.py          — inter-module communication bus
    project_manager.py   — create / list / delete project instances
    scheduler.py         — BackupScheduler: asyncio polling loop; fires restic backups on daily/weekly schedules
  ai/
    client.py            — AIClient: provider-aware (api_key → _chat_anthropic via Anthropic SDK;
                           local → _chat_local via OpenAI-compatible HTTP); _to_oai_tool() translates
                           Anthropic tool format to OpenAI function format; full tool-use loop for both paths
    mcp_client.py        — MCPClient: connects to MCP servers via stdio
    mcp_registry.py      — curated catalog of popular MCP servers
    skill_registry.py    — SkillRegistry singleton: register(), get_tools(scopes), call(), has()
    global_skills.py     — global-scope skills: list_projects, run_flow, search_logs
  ui/
    tiles.py             — TileGrid, ProjectTile, AddProjectTile, SettingsTile, ConfirmDeleteModal
    add_project_screen.py — full-screen tile grid of module types (ModuleTile) + name/desc form;
                            Custom tile always last with distinct purple styling; grid auto-sizes
    settings_screen.py   — AI provider config (api_key / local / login) + general settings;
                           Test Connection button for local provider; Verify button for api_key
    mcp_screen.py        — MCP server manager (Active / Add Servers tabs)
    base_project_screen.py — BaseProjectScreen: shared layout (top-bar, action-bar, setup-pane,
                             main-pane, output log), _run_cmd async helper, InputModal; all 12
                             non-git/localai modules subclass this
modules/
  git/                   — Git module (FULLY IMPLEMENTED)
    setup_screen.py      — 6-step wizard: name → type → credentials → git config → software → repos → clone
    project_screen.py    — repo management: pull/push/commit/info/delete per repo;
                           AddRepoModal for cloning via SSH or HTTPS URL
    git_ops.py           — subprocess wrappers for git, all return (bool, str)
    github_api.py        — async GitHub REST API (list repos, verify token)
    skills.py            — git_status, git_pull, git_push, git_commit, git_log, git_clone
  localai/               — LocalAI module (FULLY IMPLEMENTED)
    setup_screen.py      — 5-step wizard: config → AI generates script → review → install → done
    project_screen.py    — inference UI: prompt input, output log, optional negative prompt + file open
    hw_detect.py         — hardware detection (GPU via nvidia-smi/rocm-smi/lspci, RAM, CPU, OS, disk)
  custom/                — AI-first open project: CLAUDE.md viewer + conversational AI chat + user-defined shell commands
    project_screen.py    — CustomProjectScreen: two-pane layout (context | chat), dynamic command buttons,
                           graceful degradation without AI; skill_scopes=["global","custom"]
    skills.py            — custom_run_command, custom_ask
  web/                   — project_screen: Dev/Build/Test/Lint via package manager; auto-detects
                           framework from package.json; inline setup for project_path + pm
                           skills.py: web_list_scripts, web_run_script
  research/              — project_screen: note list (.md files), New Note / Search / Export URLs;
                           inline setup for topic + notes_dir
                           skills.py: research_list_notes, research_new_note, research_search
  codex/                 — project_screen: Zettelkasten note list, New Note with frontmatter skeleton,
                           Search (ripgrep), Open Vault; inline setup for vault_dir
                           skills.py: codex_list, codex_new_entry, codex_search
  journal/               — project_screen: entry list (.tex newest-first), New Entry (LaTeX template),
                           Compile Latest (pdflatex); inline setup for journal_dir + author
                           skills.py: journal_list_entries, journal_new_entry, journal_compile
  game/                  — project_screen: Godot info (game name, version, scene count), Launch Editor,
                           Run Game, Lint (gdtoolkit); inline setup for project_path + godot_bin
                           skills.py: game_scene_list, game_launch_editor, game_run
  org/                   — project_screen: .md file list by mtime, New Plan / New Diagram (Mermaid) /
                           New Schedule (Markdown table); inline setup for output_dir
                           skills.py: org_list_plans, org_new_plan, org_new_diagram
  home/                  — project_screen: HA URL + ping status, YAML config file list, Ping HA /
                           Check API (curl) / Open in Browser; inline setup for ha_url + config_dir + token
                           skills.py: home_ping, home_api_call
  streaming/             — project_screen: OBS config status, scene collection list, Launch OBS /
                           Check Logs / List Scenes; inline setup for obs_config_dir + platform + obs_bin
                           skills.py: streaming_list_scenes, streaming_launch_obs, streaming_check_logs
  vtube/                 — project_screen: pipeline display (Camera → tracker → runtime → OBS),
                           Launch Runtime / Start Tracker / Check Camera; inline setup for model_path +
                           runtime + tracker
                           skills.py: vtube_launch_runtime, vtube_start_tracker
  emulator/              — project_screen: ROM directory tree (system dirs + ROM counts), Launch
                           RetroArch / Browse by System; inline setup for rom_dir + retroarch_bin
                           skills.py: emulator_list_systems, emulator_launch
  vault/                 — project_screen: tool inventory (gpg/age/veracrypt/keepassxc-cli ✓/✗),
                           age key status, GPG List Keys / GPG Gen Key / age New Key / Encrypt File;
                           inline setup for vault_dir
                           skills.py: vault_list_gpg_keys, vault_age_key_status, vault_encrypt_file
  server/                — project_screen: service rows (name|port|type|status|Start/Stop/Logs),
                           concurrent status polling (systemd + docker), Add Service / Refresh / Docker PS;
                           inline setup for docker_compose_dir
                           skills.py: server_list_services, server_status, server_start, server_stop
projects/                — project instances (git-ignored except .gitkeep)
config/
  settings.yaml          — global config: AI provider + MCP servers (git-ignored)
  settings.example.yaml  — committed reference copy
logs/
  nexus.log              — rotating log file (git-ignored)
```

### Module system

Each directory under `modules/` is a project-type template. `project_manager.create_project()` instantiates it under `projects/<slug>/`, copying `CLAUDE.template.md` → `CLAUDE.md`.

All 16 modules have comprehensive `CLAUDE.template.md` files containing:
- **Static AI knowledge** — key software, commands, config patterns, and domain-specific reference tables
- **User fill-in sections** — commented prompts for the user to describe their specific setup

`module_manager.py` is the single dispatch point:
- `needs_setup(project) -> bool` — True if the project hasn't been configured yet
- `get_setup_screen(project)` — returns the setup `Screen` for that module
- `get_project_screen(project)` — returns the main `Screen` for an already-configured project

To add a new module, add a `ModuleInfo` entry to `_REGISTRY` and implement the conditionals in those three functions. For a module that uses `BaseProjectScreen`, subclass it in `modules/<id>/project_screen.py`, define `MODULE_KEY`, `MODULE_LABEL`, `SETUP_FIELDS`, `_compose_action_buttons()`, `_populate_content()`, and `_handle_action()`.

### Project instances

Each project lives at `projects/<slug>/`:
```
config.yaml      — project config (module-specific keys + mcp overrides)
CLAUDE.md        — per-project AI instructions (copied from module template, user-editable)
repos/           — (git module) cloned repositories
setup.sh         — (localai module) generated one-time setup script
outputs/         — (localai module) inference output files
```

### UI patterns

- **Multi-step forms**: use `_ALL_STEPS` list + `_show(step_id)` toggling `.display` on each container. Do NOT use `ContentSwitcher` (CSS height issues).
- **Async workers**: always pass the coroutine directly — `self.run_worker(self._my_async_method())`, not a lambda or method reference.
- **Blocking calls**: wrap in `asyncio.get_event_loop().run_in_executor(None, blocking_fn, args)`.
- **Modal screens**: push via `self.app.push_screen(Modal(...), callback)` — `push_screen` is on `App`, not `Screen`.
- **Button events in tiles**: call `event.stop()` in `on_button_pressed` to prevent the event from also triggering `on_click` on the parent widget.
- **Dynamic grid sizing**: set `widget.styles.height = rows * tile_height` in `on_mount` when a grid must fit all items without scrolling.
- **Custom messages**: subclass `Message` inside the widget class, post with `self.post_message(...)`, receive with `on_<widget_class>_<message_class>` naming.

### Logging

`nexus/core/logger.py` sets up a `RotatingFileHandler` writing to `logs/nexus.log` (5 MB × 3 backups). All modules get a child logger via `get("some.name")` which returns `logging.getLogger("nexus.some.name")`.

Call `setup_logging()` once at app startup (`nexus/app.py`). Every significant operation logs at appropriate levels; exceptions use `log.exception(...)` to capture tracebacks.

## MCP Integration

Nexus acts as an MCP **client** — it connects to configured MCP servers at runtime and injects their tools into Claude API calls.

### Data flow
```
config/settings.yaml  ──► ConfigManager ──► MCPClient (connects to servers)
projects/<name>/config.yaml ──►┘              └──► AIClient (passes tools to Claude)
```

### Key files
| File | Role |
|------|------|
| `nexus/core/config_manager.py` | `load_global_config()`, `save_global_config()`, `merged_mcp_servers()` |
| `nexus/ai/mcp_registry.py` | Curated catalog: `REGISTRY`, `REGISTRY_BY_ID` |
| `nexus/ai/mcp_client.py` | `MCPClient.connect_all()`, `get_tools()`, `call_tool()`, `disconnect_all()` |
| `nexus/ai/client.py` | `AIClient.chat(skill_scopes?)` — merges skill + MCP tools, full tool-use loop |
| `nexus/ui/mcp_screen.py` | Active / Add Servers tabs, guided config form |

### Config format

**Global** (`config/settings.yaml`):
```yaml
ai:
  provider: api_key        # api_key | local | login
  api_key: ""              # Anthropic API key (or set ANTHROPIC_API_KEY env var)
  local_endpoint: "http://localhost:11434"
  local_model: ""
mcp:
  servers:
    github:
      command: npx
      args: ["-y", "@modelcontextprotocol/server-github"]
      env:
        GITHUB_TOKEN: "ghp_..."
```

**Per-project** (`projects/<name>/config.yaml`):
```yaml
mcp:
  servers:             # project-specific additions
    sqlite:
      command: npx
      args: ["-y", "@modelcontextprotocol/server-sqlite", "--db-path", "./data.db"]
      env: {}
  disabled:            # opt-out of global servers for this project
    - brave-search
```

## AI Provider Configuration

Configured via the Settings screen (`s`) or directly in `config/settings.yaml`:

| Provider | How it works |
|----------|-------------|
| `api_key` | Anthropic API key → `AIClient._chat_anthropic()` via `AsyncAnthropic` |
| `local`   | OpenAI-compatible endpoint → `AIClient._chat_local()` via `httpx`; tools translated with `_to_oai_tool()`; degrades gracefully if model doesn't support function calling |
| `login`   | Claude.ai account login — browser OAuth, not yet supported in terminal UI |

`is_ai_configured(cfg=None) -> bool` in `config_manager.py` is the single source of truth for whether AI is usable — use it instead of checking for an API key directly. It handles both providers: `api_key` requires a key or `ANTHROPIC_API_KEY` env var; `local` requires both `local_endpoint` and `local_model`.

## Mycelium — Inter-Module Communication

`nexus/core/mycelium.py` — singleton `bus`, registers active project instances and routes payloads between modules.
`nexus/ai/flow_handlers.py` — implements the five default flows; `register_flow_handlers()` is called at app startup.

### Default flows
| Source | Target | Action |
|--------|--------|--------|
| `research` | `codex` | `research_to_codex` — distill findings into a knowledge entry |
| `git` | `journal` | `git_to_journal` — summarise recent commits |
| `research` | `org` | `research_to_org` — turn notes into a plan |
| `codex` | `journal` | `codex_to_journal` — reflect on a topic |
| `org` | `journal` | `org_to_journal` — log completed tasks |

**Status:** all five flows are fully implemented in `nexus/ai/flow_handlers.py` and registered at startup via `register_flow_handlers()`. Each handler reads source data, calls `_ai_synthesize()` (which respects the active AI provider), and writes output in the target module's native file format. Invoke via the `run_flow` global skill.

## AI Skills System

Skills are native Python tool functions registered inside the Nexus process and exposed to any AI model — external (Claude API) or local (Ollama / LM Studio). Unlike MCP servers, which are external processes that need configuration, skills run in-process, require no setup, and have direct access to project config and module helpers.

### Architecture

```
nexus/ai/skill_registry.py  — SkillRegistry: register, list, and call skills
modules/<id>/skills.py      — module-specific skill definitions (one file per module)
nexus/app.py                — registers global skills + module skills at startup
nexus/ai/client.py          — merges skill tools + MCP tools; dispatches tool_use responses
```

### Skill definition

Each skill is a dict + async handler pair registered on the `SkillRegistry` singleton:

```python
from nexus.ai.skill_registry import registry

registry.register(
    scope       = "git",          # "global" or a module id
    name        = "git_pull",
    description = "Pull the latest commits for a named repository.",
    schema      = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository directory name"}
        },
        "required": ["repo"],
    },
    handler     = my_async_pull_fn,   # async (args: dict) -> str
)
```

The handler receives the parsed arguments dict and must return a plain string, which is sent back to the model as a `tool_result`.

### SkillRegistry API

| Method | Description |
|--------|-------------|
| `registry.register(scope, name, description, schema, handler)` | Register one skill |
| `registry.get_tools(scopes)` | Return Anthropic-format tool dicts for the given scope list |
| `registry.call(name, args)` | Await the handler registered under `name` |
| `registry.all_scopes()` | Return all distinct registered scopes |

### Integration with AIClient

`AIClient.chat()` accepts an optional `skill_scopes` list. When provided, it calls `registry.get_tools(skill_scopes)`, merges the result with MCP tools, and passes the combined list to the model. On a `tool_use` response the client tries the skill registry first; if the tool name is not found there it falls through to `MCPClient.call_tool()`.

```python
reply = await ai_client.chat(
    messages      = conversation,
    system_prompt = project_system_prompt,
    skill_scopes  = ["global", project.module],
)
```

### Scope conventions

| Scope | When loaded |
|-------|-------------|
| `"global"` | Always — in every project and on the main screen |
| `"<module_id>"` | When a project of that module type is the active context |

Module skills files live at `modules/<id>/skills.py` and call `registry.register()` at import time. `nexus/app.py` imports each skills module at startup so that all skills are available before the first AI call.

### Global skills

| Skill | Inputs | Description |
|-------|--------|-------------|
| `list_projects` | — | Return all project names, module types, and descriptions |
| `run_flow` | `action`, `payload` | Trigger a Mycelium cross-module flow (e.g. `research_to_codex`, `git_to_journal`) |
| `search_logs` | `query?`, `n=50` | Return the last `n` log lines, optionally filtered by query |

### Module skills

All module skills require `project_slug` (the Nexus project slug) plus the additional inputs listed. Handlers load config via `load_project_config(slug)` and return a JSON string.

| Module | Skill | Additional inputs |
|--------|-------|-------------------|
| **git** | `git_status` | `repo` |
| | `git_pull` | `repo` |
| | `git_push` | `repo` |
| | `git_commit` | `repo`, `message` |
| | `git_log` | `repo`, `n=10` |
| | `git_clone` | `url`, `name?` |
| **web** | `web_list_scripts` | — |
| | `web_run_script` | `script` |
| **research** | `research_list_notes` | — |
| | `research_new_note` | `filename`, `content` |
| | `research_search` | `query` |
| **codex** | `codex_list` | — |
| | `codex_new_entry` | `title`, `content?` |
| | `codex_search` | `query` |
| **journal** | `journal_list_entries` | — |
| | `journal_new_entry` | `content?` |
| | `journal_compile` | — |
| **game** | `game_scene_list` | — |
| | `game_launch_editor` | — |
| | `game_run` | — |
| **org** | `org_list_plans` | — |
| | `org_new_plan` | `name`, `tasks?` |
| | `org_new_diagram` | `name`, `mermaid_content?` |
| **home** | `home_ping` | — |
| | `home_api_call` | `endpoint`, `method?` |
| **streaming** | `streaming_list_scenes` | — |
| | `streaming_launch_obs` | — |
| | `streaming_check_logs` | — |
| **vtube** | `vtube_launch_runtime` | — |
| | `vtube_start_tracker` | — |
| **emulator** | `emulator_list_systems` | — |
| | `emulator_launch` | `system`, `rom?` |
| **vault** | `vault_list_gpg_keys` | — |
| | `vault_age_key_status` | — |
| | `vault_encrypt_file` | `path` |
| **server** | `server_list_services` | — |
| | `server_status` | `service` |
| | `server_start` | `service` |
| | `server_stop` | `service` |
| **custom** | `custom_run_command` | `label` |
| | `custom_ask` | `question` |

### Skills vs MCP servers

| | Skills | MCP servers |
|--|--------|-------------|
| Location | In-process Python | External process (npx, Python, etc.) |
| Configuration | None — registered at startup | Requires command + env vars in settings.yaml |
| Access | Direct: project config, git_ops, Path | Via stdio protocol |
| Scope | Global or module-specific | Global (per-project overrides possible) |
| Use case | Nexus-native actions (pull repo, new note) | External integrations (GitHub API, web search) |

## Security Notes

- GitHub tokens are injected into HTTPS clone URLs at clone time only; they are never written to log files (`display_url` is kept separate from the injected URL in `git_ops.py`).
- SSH clone URLs bypass token injection entirely — authentication is handled by the system SSH agent.
- `config/settings.yaml` and `projects/` are git-ignored — credentials and personal data never leave the local machine via git.
- All user-supplied paths are resolved via `Path.expanduser()` before use.
- Stream keys and other secrets should be stored in the Vault module, not in plain-text project files.
- **LocalAI shell injection prevention**: user prompt values (`{prompt}`, `{negative_prompt}`) are replaced with `$NEXUS_PROMPT` / `$NEXUS_NEGATIVE_PROMPT` in the command string and passed via the subprocess `env=` dict — never interpolated directly into shell strings. Existing configs with `{prompt}` are auto-converted at runtime.
- **Backup paths**: all restic paths go through `_p()` (`os.path.abspath(os.path.expanduser(path))`) in `modules/backup/backup_ops.py` before subprocess calls. `restic_ensure_initialized()` auto-creates the repo directory and runs `restic init` on first use, treating "already initialized" as success.
