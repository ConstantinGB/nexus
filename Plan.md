# Plan

## Status: IMPLEMENTED (2026-04-30)

All five feature areas below have been implemented. The LocalAI Docker item is still
open (original entry was incomplete — see note at bottom).

---

## 1. Native Linux CLI Commands

**Goal:** `nexus` launches the TUI; `nexus <subcommand>` runs headlessly.

| Command             | Behaviour                                                                  |
| ------------------- | -------------------------------------------------------------------------- |
| `nexus`             | Launch the Textual TUI (unchanged default)                                 |
| `nexus list`        | Print a table of all projects (name / module / description)                |
| `nexus open <name>` | Launch TUI and auto-open the first matching project                        |
| `nexus version`     | Print the installed package version                                        |

**Files changed:**

- `nexus/app.py` — `main()` parses `sys.argv` via `argparse`; `NexusApp` accepts `open_project=` kwarg
- `nexus/cli.py` *(new)* — `cmd_list()`, `cmd_version()` headless helpers

---

## 2. Keyboard Navigation

**Goal:** Tiles on the home screen are focusable; arrow keys navigate; Enter opens.

- `ProjectTile`, `AddProjectTile`, `SettingsTile` all have `can_focus = True`
- Each tile has `:focus` CSS matching its `:hover` style
- Each tile has `on_key(event)` — Enter triggers `_open()`
- `TileGrid` BINDINGS: `up`/`left` → `focus_previous`, `down`/`right` → `focus_next`

**File changed:** `nexus/ui/tiles.py`

---

## 3. Multi-Project Tab System

**Goal:** Thin tab strip at top of every project screen; `+` to open another project; `Ctrl+Tab` to cycle.

**Design:**

- `NexusApp._tabs` — ordered list of currently open `ProjectInfo` objects
- `NexusApp._active_tab_idx` — index of the active tab
- Tile click calls `app.open_project_tab(project)` which registers the tab then pushes the screen
- Escape calls `close_project_tab(slug)` to remove the project from the tab list
- Tab click calls `app.switch_to_tab(project)` — stops terminals, `pop_screen()`, pushes new screen (switched-from tab stays in list)
- `+` button opens `ProjectPickerModal` (scrollable project list); picking one calls `switch_to_tab`
- `Ctrl+Tab` cycles via `action_next_tab()`

**Files changed / created:**

- `nexus/ui/project_tabs.py` *(new)* — `ProjectTabBar(Widget)`, `ProjectPickerModal(ModalScreen)`
- `nexus/ui/base_project_screen.py` — `compose()` yields `ProjectTabBar` after `Header`; `action_dismiss()` calls `close_project_tab`
- `nexus/ui/tiles.py` — `ProjectTile._open()` delegates to `app.open_project_tab()`
- `nexus/app.py` — tab state + `open_project_tab`, `close_project_tab`, `switch_to_tab`, `action_next_tab`; `Ctrl+Tab` binding

---

## 4. Custom Module Overhaul

**Goal:** Cleaner layout — context pane hidden by default, file explorer added, folder open button, bash shell.

- **Remove "Add Command" button** — `#btn-add-cmd` and handlers deleted; existing commands still load from config
- **Context pane hidden by default** — `display: none` on `#context-pane`; `📄 Context` button in top-bar toggles it
- **File explorer** — `DirectoryTree` widget in `#context-pane` below the CLAUDE.md log; clicking a file opens `TextEditorScreen`
- **Open Folder button** — `📁 Open Folder` in cmd-bar; calls `subprocess.Popen(open_path(...))`
- **Bash shell toggle** — `$ Shell` button in top-bar; `_launch_bash()` method added (same pattern as `BaseProjectScreen`)

**File changed:** `modules/custom/project_screen.py`

---

## 5. Research Module Overhaul

**Goal:** Per-note PDF export, CLAUDE.md excluded from exports, Export All format dialog, Export Doc with checkboxes.

- **PDF button per note** — `Button("PDF")` added between note and delete buttons; runs `pandoc note.md -o note.pdf`
- **CLAUDE.md exclusion** — notes glob filters `n.name != "CLAUDE.md"` in both `_populate_content()` and `_export_notes()`
- **Export All → dialog** — pushes `ExportAllModal` with "Markdown" / "PDF" choice before exporting
- **Export URLs → Export Doc** — button renamed; opens `ExportDocModal` with a checkbox list of all notes and "Export MD" / "Export PDF" / "Cancel" actions
- **`_export_notes(notes_dir, fmt, notes=None)`** — unified export: Markdown path unchanged; PDF: concatenate → temp `.md` → `pandoc` → `.pdf`
- **PDF dependency** — `shutil.which("pandoc")` check at use time; error notification if missing (module not blocked)

**File changed:** `modules/research/project_screen.py`

---

## Open: LocalAI Docker

The original Plan.md entry read *"Docker function should have"* — sentence incomplete.
What Docker functionality did you want to add to the LocalAI module?
