# Nexus Docker Test Chamber

A throwaway Ubuntu container for testing the out-of-the-box install experience from scratch.
The container has internet access and nothing pre-installed beyond git and curl.

> **Not part of the codebase.** `Dockerfile` and `run-docker-test.sh` are gitignored.

---

## Prerequisites

- Docker installed and running on the host machine.
- The Nexus git remote URL (GitHub, local gitea, etc.).

---

## Quick start

```bash
# From the repo root:
./tests/run-docker-test.sh
```

This builds the image (Ubuntu 24.04 + git + curl + locale) and drops you into a shell inside
the container. The container is destroyed when you exit (`--rm`).

---

## Step-by-step inside the container

### 1. Clone the repo

```bash
git clone https://github.com/<your-user>/nexus.git
cd nexus
```

### 2. Run the install script

```bash
./nexus-install.sh --direct
```

The script will:

- Detect apt as the package manager
- Install Python 3.12 and python3-venv if missing
- Download and install `uv` via the official installer (`~/.local/bin/uv`)
- Run `uv sync` to install all Python dependencies into `.venv/`
- Create `config/`, `projects/`, and `logs/` directories
- Copy `config/settings.example.yaml` → `config/settings.yaml`

Expected finish line: `Nexus installed. Run: uv run nexus`

### 3. Launch Nexus

```bash
uv run nexus
```

The TUI should open in full-colour mode. You need a terminal window of at least **80×24**.
Ideal size: **140×40** or larger to see side-by-side panes.

---

## Testing checklist

Work through these in order. Each item tests a distinct layer of the app.

### A — Core TUI

- [ ] App launches without Python tracebacks in the terminal
- [ ] Header, footer, and tile grid are visible
- [ ] Arrow-key navigation moves the focus highlight between tiles
- [ ] Press `q` → app exits cleanly (no exception dump)

### B — Settings screen

- [ ] Press `s` → Settings screen opens
- [ ] AI provider section is visible (api_key / local / login buttons)
- [ ] Enter a dummy API key and press Save — no crash
- [ ] Press Escape → back to main tile grid

### C — Project creation

- [ ] Press Enter (or click) on the `+` tile → Add Project screen opens
- [ ] All module type tiles are visible (git, web, research, codex, …, custom)
- [ ] Fill in a project name and description, pick a module, press Create
- [ ] New project tile appears on the main grid
- [ ] Press `q` then re-launch — project tile persists (config written to disk)

### D — Project screen (configure a module)

Pick any module and complete its setup form. Suggested quick ones:

| Module   | Required field(s)                       |
| -------- | --------------------------------------- |
| custom   | none — opens directly                   |
| research | `notes_dir` (any path, e.g. `~/notes`) |
| codex    | `vault_dir` (any path)                  |
| org      | `output_dir` (any path)                 |

- [ ] Setup form appears on first open
- [ ] Saving config shows the main pane (action bar + content area)
- [ ] Press Escape → main grid

### E — Chat panel (AI is optional)

Without a configured AI provider the panel should degrade gracefully.

- [ ] Open a configured project (any module)
- [ ] Press the **💬 AI** button in the top bar → chat panel slides in on the right (~50 % width)
- [ ] Press **💬 AI** again → chat panel hides, main pane expands to full width
- [ ] Type a message and press Enter (or Send):
  - With no AI configured → `[info] AI not configured…` message in chat log
  - With AI configured → `[AI] …` reply appears; text wraps within the panel (no horizontal scroll)
- [ ] Chat panel text does NOT extend past the visible width (no horizontal scrollbar)

### F — Custom project (shell commands)

- [ ] Create a custom project
- [ ] In the cmd-bar at the bottom press **+ Add Command** → input modal appears
- [ ] Enter e.g. `Echo test: echo hello` → command button appears
- [ ] Click the new button → `[cmd] $ echo hello` and `hello` appear in the chat log
- [ ] Press **⟳ Reload** → CLAUDE.md context re-reads without crash

### G — MCP screen

- [ ] Press `m` on the main grid → MCP Server Manager opens
- [ ] Two tabs visible: Active / Add Servers
- [ ] Press Escape → back to main grid

---

## Troubleshooting

| Symptom | Likely cause | Fix |
| ------- | ------------ | --- |
| `uv: command not found` after install | PATH not updated in current shell | Run `source ~/.bashrc` or `export PATH="$HOME/.local/bin:$PATH"` |
| TUI renders as garbled ASCII blocks | TERM not set to 256-colour | `export TERM=xterm-256color` then relaunch |
| TUI is very narrow / wraps strangely | Terminal window too small | Resize to ≥ 140 columns and re-run |
| `python3.12: command not found` | install script failed silently | Run `apt-get install -y python3.12 python3.12-venv` manually, then re-run install script |
| App opens but tile grid is empty | First-time run with empty `projects/` | Expected — add a project with the `+` tile |
| Exception traceback on launch | Import error or missing dep | Check `logs/nexus.log`; likely `uv sync` failed |
| Chat panel too tall on first open (unconfigured project) | `#body-row` not visible until configured | Save the module setup first — body-row shows only for configured projects |

---

## Cleaning up

The container is destroyed automatically when you type `exit` (the `--rm` flag).
The Docker image stays cached:

```bash
docker rmi nexus-test-chamber    # remove image
```

To rebuild the image from scratch (e.g. after Dockerfile changes):

```bash
./tests/run-docker-test.sh       # always rebuilds before running
```
