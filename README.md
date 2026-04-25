# Nexus

A personal project manager with a terminal UI. Nexus keeps all your projects in one place, provides AI-assisted setup and automation for each project type, and connects to external services via MCP servers.

## Philosophy

Nexus is designed to run independently of AI. Every module works out of the box — Git, backups, web dashboards, vault, emulators — without an API key, an internet connection, or a running model. AI is an optional enhancement layer: add a local model (Ollama) or an Anthropic API key and every task gets dramatically better results, but nothing breaks without it.

The goal is that a complete novice can download, install, and run Nexus with no prior context, and that a power user can take it fully offline with a portable bundle.

## Features

- **Tile-based UI** — browse and open all your projects from a single screen
- **Module system** — each project type has its own setup wizard, management screen, and AI instructions template
- **Git module** — manage multiple GitHub / self-hosted / local git repositories; pull, push, commit, view status; add repos by SSH or HTTPS URL
- **LocalAI module** — AI-assisted setup for local language models and diffusion models; Claude detects your hardware, generates a one-time setup script; inference UI with live output streaming
- **12 additional modules** — Web, Research, Codex, Journal, Game, Org, Home, Streaming, VTube, Emulator, Vault, and Server each have a functional dashboard with inline setup form, action buttons, and a live command-output log
- **AI Skills** — 53 built-in tool functions the AI can call without any configuration: pull repos, create notes, start services, run custom commands, and more
- **AI provider config** — Anthropic API key or any OpenAI-compatible local model (Ollama, LM Studio, llama.cpp); full tool-use and Mycelium flows work on both paths
- **MCP integration** — connect to MCP servers (filesystem, GitHub, web search, SQLite, and more) and inject their tools into every Claude API call
- **Per-project AI instructions** — each project gets its own `CLAUDE.md` copied from the module's template; templates include domain knowledge, key software, and prompts for the AI
- **Project deletion** — remove any project tile with a confirmation dialog
- **Structured logging** — all activity written to `logs/nexus.log` with rotation

## Requirements

- Python 3.12 or later
- [uv](https://docs.astral.sh/uv/) package manager
- `git` (for the Git module)
- An Anthropic API key or a running Ollama instance (optional — for AI features)

See [Dependencies](#dependencies) for a full list of software by module.

## Quickstart

```bash
git clone <repo-url> nexus
cd nexus
uv sync
uv run nexus
```

On first run the main tile grid appears. Press `s` to open Settings and configure your AI provider before adding projects.

## Usage

### Main screen

| Key | Action |
|-----|--------|
| `s` | Open Settings |
| `m` | Open MCP server manager |
| `q` | Quit |
| `Escape` | Go back from any screen |

Click a project tile to open it. Click **＋ Add Project** to create a new one. Click **✕** on a tile to delete that project (with confirmation). Click **⚙ Settings** to configure your AI provider.

### Adding a project

1. Click **＋ Add Project**
2. A full-screen grid of module tiles appears — click any tile to select the module type
3. Enter a name and optional description, then click **Create Project**
4. The project tile appears on the main screen — click it to open the project screen. Git and LocalAI show a multi-step setup wizard; all other modules show a short inline setup form on first use

### Deleting a project

Click the **✕** button in the top-right corner of any project tile. A confirmation dialog prevents accidental deletion. This removes the project directory and all its files.

### Adding a repository to a Git project

Open a Git project, then click **Clone / Add**. Enter a repository URL — both SSH (`git@github.com:user/repo.git`) and HTTPS (`https://github.com/user/repo.git`) are supported. The name is auto-filled from the URL. Clone progress is shown live; on success the repo appears in the list.

## Modules

| Module | Description |
|--------|-------------|
| **Git** | Manage GitHub, self-hosted, or local git repositories — 6-step wizard (PAT optional for public repos), pull/push/commit per repo, branch switch/create/delete, Open PR link for GitHub/GitLab |
| **LocalAI** | Set up and run local AI models — Claude detects hardware, generates install script, live inference UI, Test Endpoint button |
| **Custom** | AI-first open project — CLAUDE.md as system context, conversational AI chat, user-defined shell command buttons |
| **Web** | Dev/Build/Test/Lint/Install via your package manager; Run Script… picker from `package.json`; Stop button for long-running processes; auto-detects framework |
| **Research** | Note list with New Note (YAML frontmatter), ripgrep Search, URL export, Export All; configurable notes directory |
| **Codex** | Zettelkasten knowledge base — new notes with frontmatter, search with 2-line context, tag filter, open vault |
| **Journal** | LaTeX journal entries — word count in list, compile with pdflatex (error summary), Open PDF button |
| **Game** | Godot project dashboard — game name, scene count, Launch Editor, Run Game, Lint (error/warning count), Export headless |
| **Org** | Plan/diagram/schedule creator — checkbox completion tracking (N/M done), Mermaid and Markdown table templates |
| **Home** | Home Assistant dashboard — ping HA, call API (token in-process via httpx), YAML config file list |
| **Streaming** | OBS dashboard — scene collection list, Launch OBS, log tail with crash/dropped-frame warning summary |
| **VTube** | Virtual avatar pipeline (camera → tracker → runtime → OBS), launch controls, openSeeFace port config |
| **Emulator** | ROM library browser by system with counts, Launch RetroArch, Browse by System → ROM picker |
| **Vault** | Tool inventory (gpg/age/veracrypt/keepassxc-cli), GPG export/import, age encrypt/decrypt, KeePassXC list, VeraCrypt mount |
| **Server** | Service dashboard (systemd + docker) — Start/Stop/Logs/Open URL per service, Import Compose, docker stats |
| **Backup** | Encrypted, deduplicated backups via restic — snapshot picker, configurable retention/excludes, restore |

All modules open an inline setup form on first use. After saving, the main dashboard appears with action buttons and a live command-output log at the bottom. Each project also gets a `CLAUDE.md` pre-filled with domain knowledge and setup prompts.

## AI Setup

Open Settings with `s` and choose your provider under **AI Provider**:

### Anthropic API Key
Enter your key from [console.anthropic.com](https://console.anthropic.com). Use the **Verify** button to confirm it works. The key is stored in `config/settings.yaml` (git-ignored).

### Local Model
Enter the endpoint URL and model name for any OpenAI-compatible server:
- **Ollama**: `http://localhost:11434`, model e.g. `llama3.2`
- **LM Studio**: `http://localhost:1234/v1`, model as shown in the app

Use the **Test Connection** button to verify the endpoint is reachable. The local provider supports the same tool-use loop as the Anthropic path — all skills and MCP tools work. If the model doesn't support function calling, tool use is silently disabled and the model replies directly.

### Claude.ai Login
Browser-based OAuth — not yet supported in the terminal UI. Use an API key in the meantime.

## MCP Servers

Press `m` to open the MCP manager. The **Add Servers** tab shows a curated list of popular MCP servers. Click one, fill in any required credentials (API keys, tokens), and it appears under **Active Servers**. Configured servers are automatically available as tools in all Claude API calls.

Popular servers include:
- **filesystem** — read and write local files
- **github** — repos, issues, PRs (needs a GitHub token)
- **fetch** — fetch web pages
- **brave-search** — web search (needs a Brave API key)
- **sqlite** — query local SQLite databases
- **memory** — persistent key-value memory across sessions

## AI Skills

Skills are built-in tools the AI can call directly without any configuration. Unlike MCP servers (external processes you set up), skills are native Nexus functions that run in-process and are always available.

When you open a project, the AI automatically has access to two layers of skills:
- **Global skills** — available in every project
- **Module skills** — specific to the active project type

The AI uses these to act, not just advise — pulling repos, creating notes, starting services, encrypting files — all from a single conversation.

### Global skills

| Skill | What it does |
|-------|--------------|
| `list_projects` | List all your Nexus projects with type and description |
| `run_flow` | Trigger a cross-module Mycelium flow (`research_to_codex`, `git_to_journal`, `research_to_org`, `codex_to_journal`, `org_to_journal`) |
| `search_logs` | Search the application log for recent events |

### Module skills

| Module | Skills |
|--------|--------|
| **Git** | `git_status`, `git_pull`, `git_push`, `git_commit`, `git_log`, `git_clone` |
| **LocalAI** | `localai_run_inference` |
| **Web** | `web_run_script` (dev/build/test/lint), `web_list_scripts` |
| **Research** | `research_list_notes`, `research_new_note`, `research_search` |
| **Codex** | `codex_list`, `codex_new_entry`, `codex_search` |
| **Journal** | `journal_list_entries`, `journal_new_entry`, `journal_compile` |
| **Game** | `game_launch_editor`, `game_run`, `game_scene_list` |
| **Org** | `org_list_plans`, `org_new_plan`, `org_new_diagram`, `org_new_schedule` |
| **Home** | `home_ping`, `home_api_call` |
| **Streaming** | `streaming_launch_obs`, `streaming_list_scenes`, `streaming_check_logs` |
| **VTube** | `vtube_launch_runtime`, `vtube_start_tracker` |
| **Emulator** | `emulator_list_systems`, `emulator_launch` |
| **Vault** | `vault_list_gpg_keys`, `vault_age_key_status`, `vault_encrypt_file` |
| **Backup** | `backup_run_backup`, `backup_list_snapshots`, `backup_check`, `backup_restore` |
| **Server** | `server_list_services`, `server_status`, `server_start`, `server_stop`, `server_restart` |
| **Custom** | `custom_run_command`, `custom_ask` |

All module skills take the project slug as their first argument so the AI always knows which project it is acting on. Skills are registered at app startup and require no configuration.

## Security

- **LocalAI**: user prompt values are passed to inference commands via environment variables (`$NEXUS_PROMPT`, `$NEXUS_NEGATIVE_PROMPT`), never interpolated into shell strings.
- **Home Assistant token**: passed via Python `httpx` headers — never exposed in subprocess arguments visible in `ps aux`.
- **Vault age key**: public key extracted via `age-keygen -y` (the correct API) rather than comment-line parsing.
- **Backup**: `backup_run_backup` skill auto-initialises the restic repo before running, matching the UI behaviour. Repo and source paths are tilde-expanded before use.
- **Cross-platform open**: all "open file/URL" actions use `nexus.core.platform.open_path()` (`xdg-open` / `open` / `start`) rather than hard-coded `xdg-open`.
- All credentials and personal data stay on your machine — `config/settings.yaml` and `projects/` are git-ignored.

## Project Data & Privacy

All personal data stays local:

| Path | Contents | Git status |
|------|----------|------------|
| `projects/` | All project instances, repos, and AI outputs | **ignored** |
| `config/settings.yaml` | API keys, tokens, MCP credentials | **ignored** |
| `logs/nexus.log` | Application log | **ignored** |

`config/settings.example.yaml` is committed as a reference — it contains no real credentials.

## Dependencies

Everything Nexus needs that is not provided by a stock Linux install, organised by layer.
Python packages are managed by `uv` and installed automatically by `uv sync`.

| Layer | Software | How to install | Required by |
|-------|----------|----------------|-------------|
| **Runtime** | Python 3.12+ | `apt install python3.12` / `dnf install python3.12` | Core |
| **Runtime** | uv | `curl -Ls https://astral.sh/uv/install.sh \| sh` | Core |
| **Python deps** | anthropic, mcp, pyyaml, textual | `uv sync` (automatic) | Core |
| **Core** | git | `apt install git` | Git module |
| **Core** | node / npx | `apt install nodejs npm` | MCP servers (optional) |
| **Journal** | pdflatex | `apt install texlive-latex-base` | Journal module |
| **Game** | Godot Engine | [godotengine.org](https://godotengine.org/download) | Game module |
| **Streaming** | OBS Studio | `apt install obs-studio` | Streaming module |
| **Emulator** | RetroArch | `apt install retroarch` | Emulator module |
| **Vault** | gpg | `apt install gnupg` | Vault module |
| **Vault** | age | `apt install age` | Vault module |
| **Vault** | keepassxc-cli | `apt install keepassxc` | Vault module |
| **Server** | docker + compose | [docs.docker.com/engine/install](https://docs.docker.com/engine/install/) | Server module |
| **AI (local)** | ollama | `curl -fsSL https://ollama.com/install.sh \| sh` | LocalAI system module |
| **Backup** | restic | `apt install restic` | Backup module |
| **AI hw detect** | nvidia-smi | included with NVIDIA drivers | LocalAI hardware detection |
| **AI hw detect** | rocm-smi | included with AMD ROCm | LocalAI hardware detection |

Install scripts are provided to automate this process — see `nexus-install.sh` for the
core runtime, and Settings → Setup inside the app to install per-module software.

## Development

```bash
uv sync                  # install dependencies
uv add <package>         # add a runtime dependency
uv add --dev <package>   # add a dev dependency
uv run nexus             # run the app
```

See [CLAUDE.md](CLAUDE.md) for architecture documentation and coding patterns.
