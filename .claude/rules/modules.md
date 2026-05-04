---
description: Full module inventory, per-module skills, and module development conventions
paths:
  - "modules/**"
---

## Module Inventory

All modules live under `modules/<id>/`. All skill handlers accept `project_slug` plus the listed inputs and return a JSON string.

| Module | Key files | Skills |
|--------|-----------|--------|
| **calendar** | project_screen, gui_screen, skills.py (data layer: nexus/core/data/calendar.py) | `calendar_add(title,date,time?,desc?)` · `calendar_list(month?)` · `calendar_delete(event_id)` |
| **notes** | project_screen, gui_screen, skills.py (data layer: nexus/core/data/notes.py) | `notes_create(title,content?)` · `notes_search(query)` · `notes_get(title)` · `notes_update(title,content)` · `notes_delete(title)` |
| **tasks** | project_screen, gui_screen, skills.py (data layer: nexus/core/data/tasks.py) | `tasks_add(title,due?)` · `tasks_list(filter?)` · `tasks_complete(task_id)` · `tasks_delete(task_id)` |
| **git** | setup_screen (6-step wizard), project_screen, git_ops.py, github_api.py | `git_status(repo)` · `git_pull(repo)` · `git_push(repo)` · `git_commit(repo,message)` · `git_log(repo,n)` · `git_clone(url,name?)` · `git_diff(repo,staged)` · `git_stash(repo,action)` |
| **localai** | setup_screen (5-step AI-generated script), project_screen, hw_detect.py | `localai_run_inference(prompt,negative_prompt?)` |
| **custom** | project_screen (CLAUDE.md viewer + chat + shell commands) | `custom_run_command(label)` · `custom_ask(question)` |
| **web** | project_screen (package manager, scripts) | `web_list_scripts()` · `web_run_script(script)` |
| **research** | project_screen (MD notes, YAML frontmatter) | `research_list_notes()` · `research_new_note(filename,content)` · `research_search(query)` · `research_get_note(filename)` · `research_delete_note(filename)` |
| **codex** | project_screen (Zettelkasten, ripgrep search) | `codex_list()` · `codex_new_entry(title,content?)` · `codex_search(query)` · `codex_get_entry(filename)` |
| **journal** | project_screen (LaTeX entries, pdflatex compile) | `journal_list_entries()` · `journal_new_entry(content?)` · `journal_compile()` |
| **game** | project_screen (Godot: editor, run, lint, export) | `game_scene_list()` · `game_launch_editor()` · `game_run()` |
| **org** | project_screen (MD plans, Mermaid diagrams, schedules) | `org_list_plans()` · `org_new_plan(name,tasks?)` · `org_new_diagram(name,content?)` · `org_new_schedule(name)` · `org_get_plan(filename)` |
| **home** | project_screen (Home Assistant ping + API) | `home_ping()` · `home_api_call(endpoint,method?)` |
| **streaming** | project_screen (OBS scenes, logs) | `streaming_list_scenes()` · `streaming_launch_obs()` · `streaming_check_logs()` |
| **vtube** | project_screen (Camera→tracker→runtime pipeline) | `vtube_launch_runtime()` · `vtube_start_tracker()` |
| **emulator** | project_screen (ROM tree, RetroArch) | `emulator_list_systems()` · `emulator_launch(system,rom?)` |
| **vault** | project_screen (GPG/age/VeraCrypt/KeePassXC) | `vault_list_gpg_keys()` · `vault_age_key_status()` · `vault_encrypt_file(path)` · `vault_decrypt_file(path,engine)` |
| **server** | project_screen (systemd+docker service rows) | `server_list_services()` · `server_status(svc)` · `server_start(svc)` · `server_stop(svc)` · `server_restart(svc)` · `server_logs(svc,n)` |
| **backup** | project_screen + backup_ops.py (restic) | `backup_run_backup()` · `backup_list_snapshots()` · `backup_check()` · `backup_restore(snapshot?,target)` · `backup_forget(keep_last)` |
| **security** | project_screen (ufw + nmap) | *(no registered skills — guide via Chat)* |
| **sdforge** | setup_screen (5-step wizard) + project_screen + api_client.py | `sdforge_txt2img(prompt,…)` |
| **promptopt** | project_screen (3-mode optimizer, no setup) | `promptopt_optimize(prompt,mode)` |
| **youtube** | project_screen (video metadata + download) | *(see modules/youtube/skills.py)* |

## Module Development Conventions

### Adding a TUI module

1. Create `modules/<id>/` with `project_screen.py`, `skills.py`, `CLAUDE.template.md`.
2. Add `ModuleInfo` to `_REGISTRY` in `nexus/core/module_manager.py`.
3. Implement `needs_setup()`, `get_setup_screen()`, `get_project_screen()` conditionals.
4. Import `modules.<id>.skills` in `_register_skills()` in `nexus/app.py`.

### BaseProjectScreen subclass skeleton

```python
class MyProjectScreen(BaseProjectScreen):
    MODULE_KEY   = "mymodule"
    MODULE_LABEL = "My Module"
    SETUP_FIELDS = [("key", "Label", "placeholder"), ...]
    REQUIRED_BINARIES = [("somebinary", "SomeBinary")]  # or []

    def _compose_action_buttons(self):
        yield Button("Do Thing", id="do-thing")

    async def _populate_content(self) -> None:
        cfg = self._project_config()
        ...

    async def _handle_action(self, action_id: str) -> None:
        if action_id == "do-thing":
            await self._run_cmd(["sometool", "--flag"])
```

### Adding a GUI screen

Create `modules/<id>/gui_screen.py` with `GuiScreen(BaseProjectWindow)`. The tile grid dispatcher imports it via `importlib`. If `GuiScreen` is absent, `BaseProjectWindow` is used as a fallback.

### CLAUDE.template.md

Every module needs one. It's copied to `projects/<slug>/CLAUDE.md` on project creation and serves as the AI system prompt. Include: domain reference tables, key commands, user fill-in sections (commented).
