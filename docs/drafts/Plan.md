# Nexus Redesign Plan

## The Shift in One Sentence

Projects are containers of work. Modules are opt-in tools. A project hub replaces the current one-module-per-project dispatch.

---

## What Changes vs. What Stays

### Stays as-is
- All individual module `project_screen.py` (TUI) and `gui_screen.py` (GUI) — they still work as sub-screens/widgets, just launched from the hub
- AI client, skill registry, MCP integration
- Theme system and base widgets
- `BaseProjectScreen` and `ModuleGuiBase` scaffolding (possibly extended in Phase 5)
- All existing module data layers (`calendar_module.py`, `notes_module.py`, `todo_module.py`, `git_ops.py`, etc.)
- `CLAUDE.md` per-project AI context

### Changes significantly
- `ProjectInfo`: `module: str` → `modules: list[str]`
- `create_project(name, module, ...)` → `create_project(name, modules: list[str], ...)`
- TUI: new `ProjectHubScreen` replaces direct dispatch to module screens
- TUI: Chat/Claude/Shell three buttons → one `⌨` button with mode selector
- GUI: project tab redesigned around a module icon bar + swappable content area
- `AddProjectScreen` (TUI) and `_AddProjectDialog` (GUI): checkbox multi-select replaces single combo
- `modules/operator/` deleted; Calendar, Notes, Tasks become independent modules

### New files
- `nexus/ui/tui/project_hub_screen.py` — the new TUI project entry point
- `nexus/ui/gui/project_hub_widget.py` — the new GUI project entry point
- `modules/calendar/` — split from operator
- `modules/notes/` — split from operator
- `modules/tasks/` — split from operator

---

## Module Categorisation

Two categories, presented separately in the project creation UI.

### System tools (optional integrations, one config per machine)
Currently marked `system = true` or should be:
`backup`, `localai`, `sdforge`, `git`, `security`, `home`, `server`

These are project-optional (a dev project might want git + backup; a writing project probably doesn't). But you don't run two `localai` setups, and `security` is machine-wide.

`module.toml` change: add `system = true` to `git`, `security`, `home`, `server`.

### Feature modules (the actual work)
`journal`, `research`, `codex`, `youtube`, `org`, `web`, `streaming`, `vtube`, `emulator`, `vault`, `promptopt`, `game`, `custom`, **calendar**, **notes**, **tasks** (new)

---

## Data Path Convention

Every module defaults to `projects/<slug>/<module_id>/` for its data. This is already mostly true (journal, codex, emulator all write there). Modules that currently require explicit config paths (research `notes_dir`, git `repos/`) keep their config — those are external paths the user controls.

New modules calendar/notes/tasks write to:
- `projects/<slug>/calendar/` (already used by operator)
- `projects/<slug>/notes/` (already used by operator)
- `projects/<slug>/todo/` (already used by operator)

No data migration needed — paths are unchanged.

---

## Phase 1 — Project Data Model

**Goal:** `ProjectInfo.modules` exists. Old projects still load. Nothing breaks.

**Files:** `nexus/core/project_manager.py`, `nexus/core/module_manager.py`

**Changes:**
```python
# ProjectInfo gets both fields during transition
@dataclass
class ProjectInfo:
    name: str
    slug: str
    modules: list[str]          # new canonical field
    module: str                 # kept for compat — derived as modules[0] or ""
    description: str
    created_at: str
    path: Path
```

`list_projects()` handles both formats:
```python
modules = cfg.get("modules") or ([cfg["module"]] if cfg.get("module") else [])
module  = modules[0] if modules else ""
```

`create_project(name, modules: list[str], description="")` writes `modules` list to config. `module` key not written for new projects.

`_DEFAULT_SUBDIRS` keyed by module ID still works — iterate `modules` list instead of single `module`.

**`module_manager.py`:** `needs_setup(project)` and `get_setup_screen(project)` iterate `project.modules` — return setup screen for the first module in the list that needs setup (hub handles sequencing in Phase 4).

No UI changes in this phase.

---

## Phase 2 — Module Categorisation

**Goal:** `system = true` on the right modules. `list_feature_modules()` available.

**Files:** `modules/git/module.toml`, `modules/security/module.toml`, `modules/home/module.toml`, `modules/server/module.toml`, `nexus/core/module_manager.py`

**Changes:**
- Set `system = true` in the four TOMLs above
- Add `list_feature_modules() -> list[ModuleInfo]` to `module_manager.py` (inverse of `list_system_modules()`)
- Add `is_system_module(module_id: str) -> bool` helper

No UI changes in this phase.

---

## Phase 3 — Operator Split

**Goal:** `modules/operator/` is replaced by three independent modules. Existing project data is untouched.

**New modules:** `calendar`, `notes`, `tasks`

For each, the structure is:
```
modules/<id>/
  module.toml
  project_screen.py     ← extract from operator TUI (operator has no dedicated TUI tab, uses base_project_screen pattern)
  gui_screen.py         ← extract _CalendarTab / _NotesTab / _TasksTab from operator/gui_screen.py
  skills.py             ← split operator/skills.py into three
  CLAUDE.template.md
```

**`modules/calendar/module.toml`:**
```toml
[module]
id = "calendar"
label = "Calendar"
description = "Manage events and schedules."
tags = ["productivity"]
system = false
prefix = "cal"
```

Same pattern for `notes` and `tasks`.

**TUI screens:** `CalendarProjectScreen`, `NotesProjectScreen`, `TasksProjectScreen` are thin wrappers using `BaseProjectScreen` with minimal `SETUP_FIELDS = []`. They surface the same CRUD operations the operator's sub-panels had.

**GUI screens:** The existing `_CalendarTab`, `_NotesTab`, `_TasksTab` classes move to their respective `gui_screen.py` files. `GuiScreen` wraps the tab widget directly. Clean extraction — no logic changes.

**Skills:** `modules/operator/skills.py` splits into three files. The skill scopes change from `"operator"` to `"calendar"`, `"notes"`, `"tasks"`.

**Deletion:** `modules/operator/` removed. `modules/operator/calendar_module.py`, `notes_module.py`, `todo_module.py` stay as-is (they are data layers, not UI), copied/moved to the new module dirs or left in a shared `nexus/data/` location.

> **Decision point:** Move the data layer files to a shared `nexus/core/data/` location so all three modules import from one place, avoiding duplication. This keeps them out of any single module's namespace.

---

## Phase 4 — TUI Hub Screen

**Goal:** Opening a project shows a hub with all active modules, not a single module screen. Three chat buttons become one.

### `nexus/ui/tui/project_hub_screen.py`

```
ProjectHubScreen
  Header
  ProjectTabBar                       (unchanged)
  top-bar: [project name] [⚙ Config] [⌨ Input]
  module-grid: one button per active module
  body-row:
    main-pane: (empty until module selected)
    terminal-panel: (for Claude/Shell)
  ChatPanel (for AI mode)
  Footer
```

- Module buttons are generated from `project.modules`
- Clicking a module button: `self.app.push_screen(get_project_screen_for_module(project, module_id))`
- `get_project_screen_for_module(project, module_id)` is a new helper in `module_manager.py` that loads `modules/<id>/project_screen.py` for a project — same as today's `get_project_screen()` but takes explicit module ID

### Config button — module selector modal
Opens `ModuleSelectorModal(project)`:
- Two sections: Feature Modules (checkboxes) and System Tools (checkboxes)
- Save updates `project.modules` in config.yaml
- Hub refreshes its button grid on dismiss

### `⌨` Input button — replaces the three chat buttons
Opens `InputModeModal`:
```
┌─────────────────────┐
│  💬 AI Chat         │
│  ⌨  Claude          │
│  $  Shell           │
└─────────────────────┘
```
Selecting one toggles the appropriate panel (same panels as today — ChatPanel or terminal widget). The modal is a tiny `ModalScreen`, dismissed as soon as a choice is made.

> Note: this is where the deferred Issue 5 (`_SetupForm` extraction) becomes relevant. The hub will inline setup forms for modules that haven't been configured yet before pushing their screen. Extracting `_SetupForm` from `BaseProjectScreen` into a reusable widget makes that clean.

### `AddProjectScreen` update
Replace the single module combobox with:
- Section "Features" — `SelectionList` of feature modules (multi-select)
- Section "System Tools" — `SelectionList` of system modules (multi-select, collapsed by default)
- `create_project(name, modules=[...])` on confirm

### `module_manager.py` additions
```python
def get_project_screen_for_module(project: ProjectInfo, module_id: str):
    """Load ProjectScreen for a specific module within a multi-module project."""
    mod = importlib.import_module(f"modules.{module_id}.project_screen")
    cls = getattr(mod, "ProjectScreen", None)
    return cls(project) if cls else None
```

---

## Phase 5 — GUI Hub

**Goal:** GUI project tabs use a module icon bar + swappable content area. Chat becomes a collapsible `⌨` panel.

### `nexus/ui/gui/project_hub_widget.py`

```
ProjectHubWidget(QWidget)
  left_bar: QWidget (fixed ~48px wide)
    ModuleIconButton per active module (vertical stack)
    spacer
    InputButton (⌨ icon)
  content_area: QStackedWidget
    one widget per module (lazy-loaded on first click)
  input_panel: QWidget (right side, collapsible)
    mode selector (AI Chat | Claude | Shell)
    actual panel (ChatPanel or PtyTerminalWidget)
```

**`ModuleIconButton`:** `QPushButton` with icon or two-letter label, tooltip = module name. Clicking emits `module_selected(module_id)` signal.

**Module widget loading:** On first click of a module button, `importlib` loads `gui_screen.py` for that module and constructs `GuiScreen(project)`. Cached in a dict — subsequent clicks just switch the stacked widget index.

**`⌨` InputButton:**
- Toggles `input_panel` visibility
- A small settings gear icon on the panel header lets user pick AI / Claude / Shell
- Panel uses the existing `ChatPanel` (AI) or `PtyTerminalWidget` ("claude" or "bash -i")

**`NexusGuiApp._open_project()` change:**
Replace the current per-module `gui_screen.py` dispatch with `ProjectHubWidget(project)` unconditionally. The hub itself handles per-module dispatch. This simplifies `_open_project()` significantly.

**`_AddProjectDialog` update:**
Replace `QComboBox` (single module) with two `QListWidget` with checkboxes — Feature modules and System Tools — same categorisation as TUI.

### Cleanup after Phase 5
- `nexus/ui/gui/base_project_window.py` can gain a `project_dir` property: `Path("projects") / self.project.slug / module_id` helper used by module widgets
- The per-project `gui_screen.py` override path (`projects/<slug>/gui_screen.py`) in `app.py` can be removed or kept for power users

---

## Deferred (Issues 4 & 5 from Earlier Assessment)

**Issue 4 — `_McpPanel` extraction:** Still valuable, most relevant when both settings dialog and any per-module MCP config UI are consolidated during Phase 4/5.

**Issue 5 — `_SetupForm` extraction from `BaseProjectScreen`:** Directly needed for Phase 4 — the hub screen needs to render setup forms inline before pushing module screens. Extract `_SetupForm` as a standalone `Widget` that `BaseProjectScreen` and `ProjectHubScreen` both use.

---

## Execution Order and Risk

| Phase | Work size | Risk | Dependency |
|-------|-----------|------|------------|
| 1 | Small | Low (compat layer) | None |
| 2 | Tiny | None | None |
| 3 | Medium | Low (data paths unchanged) | Phase 1 |
| 4 | Large | Medium (new TUI screen) | Phases 1–3 |
| 5 | Large | Medium (new GUI widget) | Phases 1–3 |

Phases 4 and 5 are independent of each other — can be done in parallel or in either order.

Phases 1 and 2 can be done in the same commit. Phase 3 can follow immediately. The user explicitly said old projects can be dropped.

## What We're NOT Doing
- Converting existing `projects/` data — new model, fresh start
- Supporting the old `module: str` config key beyond a one-time read compat shim
- A general plugin system — modules are still first-class code, not hot-loadable plugins
