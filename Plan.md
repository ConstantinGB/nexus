# Nexus Improvement Plan

---

## Task 1 — Prompt Optimizer Module

### Goal
New module `promptopt` that takes user input text, applies an AI optimization pass in one of three modes, and returns an enhanced prompt the user can copy.

### Files to create / modify

**Create `modules/promptopt/`:**
- `project_screen.py` — `PromptOptProjectScreen(BaseProjectScreen)`
- `skills.py` — `promptopt_optimize` skill
- `CLAUDE.template.md` — AI context for the module

**Modify `nexus/core/module_manager.py`:**
- Add to `_REGISTRY`:
  ```python
  ModuleInfo("promptopt", "Prompt Opt", "Optimize and rewrite prompts for AI clarity, instructions, or image generation.", ["ai", "tools"]),
  ```
- Add to `MODULE_PREFIX`: `"promptopt": "pro"`
- Add dispatch in `get_project_screen()` for `"promptopt"` → `PromptOptProjectScreen`
- `needs_setup()`: returns `False` always (no setup required — AI is optional, falls back to basic rewrite rules)

**Modify `nexus/app.py`:**
- Import `modules.promptopt.skills` alongside other skills imports

### `project_screen.py` spec

```
MODULE_KEY   = "promptopt"
MODULE_LABEL = "PROMPT OPT"
SETUP_FIELDS = []   # no setup required
```

Layout (in `_populate_content`):
1. Mode selector row — three `Button` widgets: `"Text"` (`id="btn-mode-text"`), `"Instruct"` (`id="btn-mode-instruct"`), `"Image"` (`id="btn-mode-image"`). Active mode button gets `variant="primary"`, others default.
2. `Input` widget (`id="input-prompt"`, placeholder `"Enter your prompt here…"`)
3. `Button("Optimize", id="btn-optimize", variant="primary")`
4. Output `Label` or `TextArea` (`id="output-area"`) — starts empty, read-only display
5. `Button("Copy", id="btn-copy")` — disabled until output is populated; calls `self.app.copy_to_clipboard(output_text)`

State: `self._mode: str = "text"` (default). Clicking a mode button sets `self._mode` and refreshes button variants.

Mode system prompts passed to AIClient:
- `"text"` → `"Rewrite the following prompt to be more precise, unambiguous, and AI-readable. Return only the improved prompt, no explanation."`
- `"instruct"` → `"Rewrite the following as a clear AI instruction. Use imperative tone, explicit constraints, and structured formatting. Return only the rewritten instruction."`
- `"image"` → `"Convert the following natural-language image description into a comma-separated tag-based prompt optimised for Stable Diffusion. Include style, lighting, composition, and quality tags. Return only the tag prompt."`

If AI is not configured (`not is_ai_configured()`): notify the user with `severity="warning"` — `"AI not configured — open Settings to add an API key or local model."` and do not run the request.

### `skills.py` spec

```python
registry.register(
    scope       = "promptopt",
    name        = "promptopt_optimize",
    description = "Optimize a prompt for a given mode: text, instruct, or image.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "prompt":       {"type": "string", "description": "The raw input prompt to optimize"},
            "mode":         {"type": "string", "enum": ["text", "instruct", "image"],
                             "description": "Optimization mode"},
        },
        "required": ["project_slug", "prompt", "mode"],
    },
    handler = _promptopt_optimize,
)
```

Handler calls `AIClient.chat()` with the appropriate system prompt and returns the optimized text as a plain string.

---

## Task 2 — macchanger Install Fix

### Problem
`nexus/ui/settings_screen.py` line 110:
```python
"macchanger": "sudo apt install -y macchanger",
```
`apt install macchanger` triggers an interactive debconf dialog asking whether macchanger should randomize MAC on boot. This freezes the install inside Nexus's `_run_install` terminal because stdin is a pipe, not a TTY.

### Fix
Change line 110 to:
```python
"macchanger": "DEBIAN_FRONTEND=noninteractive sudo apt install -y macchanger",
```
This suppresses the debconf dialog and uses the package default (no automatic randomization at boot), which is the safe non-destructive choice.

**File:** `nexus/ui/settings_screen.py`, line 110.

**Acceptance:** clicking Install next to macchanger in Settings > Setup runs to completion without hanging.

---

## Task 3 — Missing-Software Popup on Module Open

### Goal
When a module's project screen opens and one or more required binaries are absent, immediately show a modal listing the missing tools with an "Open Settings" button that navigates to Settings > Setup tab.

### Design decisions
- The check runs once in `BaseProjectScreen.on_mount` (after `call_after_refresh`), not on every refresh.
- Each module subclass declares its requirements via a new class attribute:
  ```python
  REQUIRED_BINARIES: list[tuple[str, str]] = []
  # Each tuple: (binary_to_shutil_which, human_readable_display_name)
  ```
- The modal is **non-blocking**: it uses `push_screen` with a callback — the user dismisses it and the screen remains usable.
- Navigation to Settings passes `initial_tab="tab_setup"` to `SettingsScreen` so the Setup tab is pre-selected.

### Files to modify

**`nexus/ui/base_project_screen.py`**

1. Add `REQUIRED_BINARIES: list[tuple[str, str]] = []` as a class variable on `BaseProjectScreen`.

2. Add `MissingDepsModal(ModalScreen)` class (before `BaseProjectScreen`):
   ```
   Title: "Missing Software"
   Body: bulleted list of missing binary display names
   Buttons: "Open Settings" (variant="primary"), "Dismiss"
   On "Open Settings": dismiss modal, then self.app.push_screen(SettingsScreen(initial_tab="tab_setup"))
   ```

3. In `BaseProjectScreen.on_mount`, after the existing `call_after_refresh` block:
   ```python
   self.call_after_refresh(self._check_required_binaries)
   ```

4. Add `_check_required_binaries(self)` method:
   ```python
   import shutil
   missing = [(bin_, name) for bin_, name in self.REQUIRED_BINARIES if not shutil.which(bin_)]
   if missing:
       self.app.push_screen(MissingDepsModal([name for _, name in missing]))
   ```

**Module screens** — add `REQUIRED_BINARIES` to each subclass:

| Module file | `REQUIRED_BINARIES` |
|---|---|
| `modules/git/project_screen.py` | `[("git", "Git")]` |
| `modules/web/project_screen.py` | `[("node", "Node.js"), ("npm", "npm")]` |
| `modules/research/project_screen.py` | `[("rg", "ripgrep")]` |
| `modules/codex/project_screen.py` | `[("rg", "ripgrep")]` |
| `modules/journal/project_screen.py` | `[("pdflatex", "pdflatex (texlive-latex-base)")]` |
| `modules/streaming/project_screen.py` | `[("obs", "OBS Studio")]` |
| `modules/emulator/project_screen.py` | `[("retroarch", "RetroArch")]` |
| `modules/vault/project_screen.py` | `[("gpg", "GnuPG"), ("age", "age"), ("keepassxc-cli", "KeePassXC CLI")]` |
| `modules/server/project_screen.py` | `[("docker", "Docker")]` |
| `modules/backup/project_screen.py` | `[("restic", "restic")]` |
| `modules/security/project_screen.py` | `[("ufw", "ufw"), ("nmap", "nmap")]` |

Modules with no required system binaries (custom, org, home, game, localai, vtube, sdforge, promptopt) leave `REQUIRED_BINARIES = []` (the default) and require no changes.

**Acceptance:** Opening the Security module on a system without `ufw` immediately shows the modal listing "ufw". Clicking "Open Settings" opens SettingsScreen on the Setup tab. Clicking "Dismiss" closes the modal and shows the module normally.

---

## Task 4 — CLAUDE.template.md Audit & Local Model Uplift

### Goal
Every module's `CLAUDE.template.md` must be accurate for its current feature set and include a **Local Model** section giving explicit guidance for when Claude API is unavailable.

### Scope
All 18 template files in `modules/*/CLAUDE.template.md`.

### Audit checklist per template
1. **Accuracy** — does the template correctly describe the module's current skills, config keys, and output paths? Update anything that drifted since initial implementation.
2. **Local model section** — add (or update) a `## Local Model Guidance` section covering:
   - Which skills work reliably with local models and which may fail due to limited tool-calling
   - Recommended prompt style: explicit, structured, one-task-at-a-time
   - Output format instructions: `"Return JSON"` or `"Return only the result, no explanation"` where applicable
   - Fallback: if the model doesn't respond with a tool call, how to re-prompt manually
3. **Tool reference table** — each template must have an up-to-date table of its registered skills with input parameters and one-line descriptions.
4. **User fill-in prompts** — keep the commented `<!-- fill in your ... -->` sections; ensure they exist for all module-specific config (paths, usernames, preferences).

### Priority order
Start with modules that have AI-heavy workflows or recently added features:
1. `modules/custom/CLAUDE.template.md` — AI-first module, needs thorough local model section
2. `modules/research/CLAUDE.template.md` — heavy use of note creation, search
3. `modules/codex/CLAUDE.template.md` — Zettelkasten workflows
4. `modules/localai/CLAUDE.template.md` — local model context is core to the module
5. `modules/git/CLAUDE.template.md` — most skills, verify all are documented
6. All remaining 13 in any order

---

## Task 5 — Skill Expansion

### Goal
Add missing but obviously useful skills to existing modules. Priority: skills that a user would naturally ask an AI to do but that currently require manual UI interaction.

### Additions per module

**`modules/research/skills.py`**
- `research_get_note` — read and return the full content of a named note (`filename` arg)
- `research_delete_note` — delete a note file by name (with safety: return error if file does not exist, never delete outside notes_dir)

**`modules/codex/skills.py`**
- `codex_get_entry` — read full content of a named entry

**`modules/git/skills.py`**
- `git_diff` — return `git diff` or `git diff HEAD` output for a repo (`repo` arg, optional `staged: bool`)
- `git_stash` — run `git stash` or `git stash pop` (`repo`, `action: "push"|"pop"`)

**`modules/org/skills.py`**
- `org_get_plan` — read and return full content of a named plan file

**`modules/vault/skills.py`**
- `vault_decrypt_file` — decrypt a file with age or gpg, return plaintext path (`path`, `engine: "age"|"gpg"`)

**`modules/server/skills.py`**
- `server_logs` — return last N lines of a service's docker/systemd logs (`service`, `n=50`)

**`modules/backup/skills.py`**
- `backup_forget` — run `restic forget` with a retention policy (`keep_last: int`)

### Implementation pattern (all new skills)
Follow existing pattern in the same `skills.py` file:
- Wrap all file I/O in `asyncio.to_thread`
- Use `load_project_config(slug)` to get paths; never hardcode
- Return `json.dumps({"error": "..."})` on failure, never raise
- Add to module's `CLAUDE.template.md` tool table after implementing
