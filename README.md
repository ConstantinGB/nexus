# Nexus

A personal project manager with a tile-based terminal UI and an optional PySide6 desktop GUI. Nexus integrates AI (Claude API or any local model via OpenAI-compatible endpoint) and connects to external tools via MCP servers.

## Philosophy

Projects are containers of work. Modules are opt-in tools — a project can activate any combination. Create a project, tick the modules you need, and each one reads and writes to that project's directory.

AI is a progressive enhancement — all modules work without an API key. Git, backups, the vault, the server dashboard, the emulator — everything runs offline. Add an Anthropic API key or a local Ollama model and every task gets dramatically better results, but nothing breaks without one.

## Features

- **Dual interface** — Textual TUI (SSH-friendly, no X11 needed) and PySide6 desktop GUI (`--gui`)
- **Tile grid** — all projects on one screen; click to open, `✕` to delete with confirmation
- **22 modules** — feature modules (calendar, notes, tasks, journal, research, …) and system tools (git, backup, localai, …); any combination per project
- **Project hub** — opening a project shows all its active modules as buttons; switch between them without leaving the project
- **75+ built-in skills** — the AI can act, not just advise: pull repos, create notes, run backups, encrypt files, control services, and more
- **7 colour themes** — Nexus Legacy, Vaporwave Red/Blue/Green, Midnight Amber, Neon Pink, Terminal Mono; switch live from Settings
- **MCP integration** — connect filesystem, GitHub, web search, SQLite, and custom MCP servers; their tools inject into every AI call
- **Per-project AI context** — each project gets a `CLAUDE.md` pre-filled with domain knowledge and setup prompts
- **Clipboard paste** — `Ctrl+V` in every input field (xclip / wl-clipboard / pbpaste)
- **Structured logging** — `logs/nexus.log` with rotation

## Quickstart

```bash
git clone <repo-url> nexus
cd nexus
./nexus-install.sh        # interactive installer
uv run nexus              # TUI
uv run nexus --gui        # desktop GUI
```

Or manually:

```bash
uv sync
uv run nexus
```

Press `s` on the main screen to open Settings and configure your AI provider.

## CLI reference

```bash
uv run nexus                      # Textual TUI (default)
uv run nexus --gui                # PySide6 desktop GUI
uv run nexus open "my project"    # TUI with a project pre-opened
uv run nexus list                 # list all projects (no UI)
uv run nexus version              # print version
uv run nexus install-desktop      # install GUI taskbar launcher
```

## TUI keyboard shortcuts

| Key | Action |
| --- | ------ |
| `s` | Settings |
| `m` | MCP server manager |
| `g` | Launch GUI (opens desktop window alongside TUI) |
| `q` | Quit |
| `Escape` | Go back |
| `Ctrl+Tab` | Next open project tab |
| `Alt+←/→` | Previous / next tab |

## Installer (`nexus-install.sh`)

```bash
./nexus-install.sh                 # interactive menu
./nexus-install.sh --direct        # install from internet
./nexus-install.sh --local         # install from ./offline-packages/
./nexus-install.sh --download-only # download packages only (offline/portable use)
./nexus-install.sh --install-desktop  # install GUI icon + .desktop launcher
./nexus-install.sh --install-shell    # install 'nexus' shell command to ~/.local/bin
```

The interactive installer prompts for:

- **Scope** — Minimum (Python + uv + Nexus libraries) or Full (all module tools)
- **Desktop launcher** — installs `.desktop` + icon so Nexus appears in your app menu and can be pinned to the taskbar
- **Shell command** — symlinks `~/.local/bin/nexus` so you can type `nexus` without `uv run`

## Modules

### Feature modules

| Module | Description |
| ------ | ----------- |
| **Calendar** | Events and schedules — add, list, delete events per project |
| **Notes** | Markdown notes — create, search, edit, delete |
| **Tasks** | To-do list — add, complete, delete tasks |
| **Research** | Markdown notes with YAML frontmatter — list, search, new note, URL export, delete |
| **Codex** | Zettelkasten knowledge base — frontmatter notes, ripgrep search with context, tag filter |
| **Journal** | LaTeX journal — word count per entry, pdflatex compile with error summary, Open PDF |
| **Org** | Plans, Mermaid diagrams, schedules — checkbox completion tracking, Markdown templates |
| **Web** | Dev server / build — package manager detection, `package.json` script picker, Stop button |
| **Game** | Godot project dashboard — scene count, Launch Editor, Run, lint, headless export |
| **Streaming** | OBS Studio — scene list, Launch OBS, log tail with crash/dropped-frame warnings |
| **VTube** | Virtual avatar pipeline — camera → openSeeFace tracker → runtime → OBS launch controls |
| **Emulator** | ROM library by system with counts, Launch RetroArch, per-system ROM picker |
| **Vault** | GPG, age, VeraCrypt, KeePassXC — key management, encrypt/decrypt, path-containment guard |
| **YouTube** | Video metadata, download video/audio, fetch transcripts via yt-dlp |
| **Prompt Opt** | AI prompt optimizer — Text / Instruct / Image (SD tags) modes, Copy button |
| **Custom** | Open-ended AI project — `CLAUDE.md` context viewer, chat, shell command buttons |

### System tools

These are machine-level integrations — typically one per machine, shared across projects.

| Module | Description |
| ------ | ----------- |
| **Git** | Multi-repo manager — clone (SSH/HTTPS), pull/push/commit/diff/stash, branch management |
| **Backup** | Encrypted, deduplicated backups via restic — snapshot picker, retention config, restore |
| **Local AI** | Set up and run local models — hardware detection, AI-generated install script, live inference UI |
| **SD Forge** | Stable Diffusion via Forge API — txt2img with configurable models, samplers, and parameters |
| **Home** | Home Assistant — ping, REST API calls (token via httpx headers, never in `ps`), YAML config |
| **Server** | systemd + Docker service dashboard — Start/Stop/Logs/Open URL per service, docker stats |
| **Security** | ufw firewall status, nmap scanning, guided security checks via AI chat |

## AI setup

Open Settings (`s`) and choose a provider under **AI Provider**.

### Anthropic API key

Enter your key from [console.anthropic.com](https://console.anthropic.com). Use **Verify** to confirm it works. Stored in `config/settings.yaml` (git-ignored).

### Local model

Enter an endpoint URL and model name for any OpenAI-compatible server:

- **Ollama** — `http://localhost:11434`, model e.g. `llama3.2`
- **LM Studio** — `http://localhost:1234/v1`, model as shown in the app

Use **Test Connection** to verify. The local path supports the same tool-use loop as Anthropic — all skills and MCP tools work.

## AI skills

Skills are built-in tools the AI can call without any configuration. When you open a project the AI gets two layers:

- **Global** — available in every project
- **Module** — specific to the modules active in the project

### Global skills

| Skill | Description |
| ----- | ----------- |
| `list_projects` | List all Nexus projects |
| `run_flow` | Trigger a cross-module Mycelium flow |
| `search_logs` | Search the application log |

### Module skills

| Module | Skills |
| ------ | ------ |
| **Calendar** | `calendar_add` · `calendar_list` · `calendar_delete` |
| **Notes** | `notes_create` · `notes_search` · `notes_get` · `notes_update` · `notes_delete` |
| **Tasks** | `tasks_add` · `tasks_list` · `tasks_complete` · `tasks_delete` |
| **Git** | `git_status` · `git_pull` · `git_push` · `git_commit` · `git_log` · `git_clone` · `git_diff` · `git_stash` |
| **Local AI** | `localai_run_inference` |
| **Custom** | `custom_run_command` · `custom_ask` |
| **Web** | `web_list_scripts` · `web_run_script` |
| **Research** | `research_list_notes` · `research_new_note` · `research_search` · `research_get_note` · `research_delete_note` |
| **Codex** | `codex_list` · `codex_new_entry` · `codex_search` · `codex_get_entry` |
| **Journal** | `journal_list_entries` · `journal_new_entry` · `journal_compile` |
| **Game** | `game_scene_list` · `game_launch_editor` · `game_run` |
| **Org** | `org_list_plans` · `org_new_plan` · `org_new_diagram` · `org_new_schedule` · `org_get_plan` |
| **Home** | `home_ping` · `home_api_call` |
| **Streaming** | `streaming_list_scenes` · `streaming_launch_obs` · `streaming_check_logs` |
| **VTube** | `vtube_launch_runtime` · `vtube_start_tracker` |
| **Emulator** | `emulator_list_systems` · `emulator_launch` |
| **Vault** | `vault_list_gpg_keys` · `vault_age_key_status` · `vault_encrypt_file` · `vault_decrypt_file` |
| **Server** | `server_list_services` · `server_status` · `server_start` · `server_stop` · `server_restart` · `server_logs` |
| **Backup** | `backup_run_backup` · `backup_list_snapshots` · `backup_check` · `backup_restore` · `backup_forget` |
| **SD Forge** | `sdforge_txt2img` |
| **YouTube** | `youtube_fetch_info` · `youtube_download_video` · `youtube_download_audio` · `youtube_get_transcript` |
| **Prompt Opt** | `promptopt_optimize` |

## MCP servers

Press `m` to open the MCP manager. The **Add Servers** tab shows a curated catalog. Click a server, fill in credentials, and it appears under **Active Servers** — its tools are automatically available in all AI calls.

Popular servers: `filesystem`, `github`, `fetch`, `brave-search`, `sqlite`, `memory`.

## Themes

Seven colour themes, switchable live from Settings → Appearance (no restart required):

- **Nexus Legacy** — cyan / purple (default)
- **Vaporwave Red / Blue / Green**
- **Midnight Amber**
- **Neon Pink**
- **Terminal Mono**

## Project data and privacy

All personal data stays local:

| Path | Contents | Git status |
| ---- | -------- | ---------- |
| `projects/` | Project instances, repos, notes, AI outputs | **ignored** |
| `config/settings.yaml` | API keys, tokens, MCP credentials | **ignored** |
| `logs/nexus.log` | Application log | **ignored** |

`config/settings.example.yaml` is committed as a reference — no real credentials.

## Security notes

- Prompt values for LocalAI passed via `$NEXUS_PROMPT` env var — never interpolated into shell strings
- Home Assistant token passed via `httpx` headers — never visible in `ps aux`
- Vault operations resolve file paths with `Path.resolve()` and verify they stay inside the vault directory (path traversal prevention)
- SDForge launch args split with `shlex.split` and passed as an arg list — no shell injection from config
- Docker daemon verified running (not just binary present) before any container operation
- Containers started by Nexus are tracked and stopped cleanly on exit

## Dependencies

Python packages are managed by `uv sync` automatically.

| Layer | Software | Install | Required by |
| ----- | -------- | ------- | ----------- |
| **System** | xclip | `apt install xclip` | Clipboard (X11) |
| **System** | wl-clipboard | `apt install wl-clipboard` | Clipboard (Wayland) |
| **Runtime** | Python 3.12+ | `apt install python3.12` | Core |
| **Runtime** | uv | `curl -Ls https://astral.sh/uv/install.sh \| sh` | Core |
| **Module** | git | `apt install git` | Git module |
| **Module** | ripgrep (`rg`) | `apt install ripgrep` | Codex / Research search |
| **Module** | pdflatex | `apt install texlive-latex-base` | Journal module |
| **Module** | Godot Engine | [godotengine.org](https://godotengine.org/download) | Game module |
| **Module** | OBS Studio | `apt install obs-studio` | Streaming module |
| **Module** | RetroArch | `apt install retroarch` | Emulator module |
| **Module** | gpg | `apt install gnupg` | Vault module |
| **Module** | age | `apt install age` | Vault module |
| **Module** | KeePassXC | `apt install keepassxc` | Vault module |
| **Module** | Docker + Compose | [docs.docker.com](https://docs.docker.com/engine/install/) | Server / LocalAI modules |
| **Module** | restic | `apt install restic` | Backup module |
| **Module** | Ollama | `curl -fsSL https://ollama.com/install.sh \| sh` | LocalAI module |
| **Module** | yt-dlp | installed via `uv sync` | YouTube module |
| **Module** | node / npx | `apt install nodejs npm` | MCP servers (optional) |

Use `./nexus-install.sh --direct` with scope **Full** to install all system packages automatically.

## Development

```bash
uv sync                  # install / update dependencies
uv add <package>         # add a runtime dependency
uv run nexus             # run the app
```

See [CLAUDE.md](CLAUDE.md) for architecture documentation and coding patterns.
