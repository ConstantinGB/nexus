# Implementation Plan — Session May 5th 2026

## Part 1: Project Setup Improvements

### 1a. Module Auto-Setup on Add
**Problem:** `create_project()` creates module subdirs via `_DEFAULT_SUBDIRS`, but adding a module later via Config does not.

- `nexus/core/project_manager.py` — extract `ensure_module_dirs(project_path, module_id)` from create logic; call from `create_project()`.
- `nexus/ui/tui/project_hub_screen.py` — after `ModuleSelectorModal` updates `project.modules`, call `ensure_module_dirs` for each newly-added module.
- GUI Config dialog (1c) — same call.

### 1b. Custom Project Path
**Problem:** Projects are always at `projects/<slug>/` with no override.

- `nexus/core/project_manager.py`:
  - Optional `custom_path` in `config.yaml`.
  - `ProjectInfo.path` property: `custom_path if set else PROJECTS_DIR / slug`.
  - `update_project_path(slug, new_path)` — updates config only.
  - `move_project_files(slug, new_path)` — moves dir tree, updates config.
- `nexus/ui/tui/base_project_screen.py` — add Path Input to `EditProjectModal`; on save, if changed, show move-confirmation modal.
- GUI Config dialog (1c) handles path the same way.

### 1c. GUI Config Button (all-in-one)
**Problem:** GUI has no Config or Edit button on the project hub.

- `nexus/ui/gui/project_hub_widget.py`:
  - Add `QPushButton("⚙")` above the `⌨` button in the left sidebar.
  - `_ProjectConfigDialog(QDialog)` with: Name, Description, two-list module selector (active/available + Add/Remove), Path + Browse.
  - On Accept: update meta if changed → `ensure_module_dirs` for added modules → if path changed, `QMessageBox` "Move files?" → Yes: `move_project_files` / No: `update_project_path`.

### 1d. Module Setup Wizard in GUI on First Open
**Problem:** TUI checks `needs_setup_for_module` before opening a module; GUI does not.

- `nexus/ui/gui/project_hub_widget.py` — in `_load_module_widget(module_id)`: call `needs_setup_for_module`; if True, load `setup_screen.SetupScreen` and show it; on completion callback swap to the real GuiScreen.

---

## Part 2: Codex Overhaul

Codex is repurposed from Zettelkasten vault → **cross-module document explorer + PDF compiler**.

### Sources
Active modules in the project are scanned for text files:
| Module | Path | Extensions |
|---|---|---|
| Journal | `journal_dir/entries/**` | `.tex` |
| Notes | `projects/<slug>/data/notes/` | `.md` |
| Research | `notes_dir/**` | `.md` |
| Org | `output_dir/**` | `.md` |
| YouTube | transcript dir `**` | `.txt`, `.md` |

### Behaviour
- File list with per-file checkboxes, grouped by source module (filter tabs in TUI).
- Preview pane: Markdown rendered; LaTeX/plain text shown as raw.
- **To PDF**: collect checked files → reorder dialog (Up/Down) → `pandoc <files> -o output.pdf --pdf-engine=xelatex` → save to `projects/<slug>/codex/`.

### TUI Layout
```
┌─ Codex ──────────────────────────────────────────────────────────┐
│ [Journal] [Notes] [Research] [Org] [YouTube]  (source tabs)      │
├───────────────┬──────────────────────────────────────────────────┤
│ ☑ entry1.tex │ (preview pane)                                    │
│ ☐ entry2.tex │                                                   │
│ ☑ note_a.md  │                                                   │
├───────────────┴──────────────────────────────────────────────────┤
│  [To PDF]   3 checked                                            │
└──────────────────────────────────────────────────────────────────┘
```
Reorder modal: `ModalScreen` with `ListView` + Up/Down buttons.

### GUI Layout
- Left: `QTreeWidget` with checkboxes, grouped by source module.
- Right: `QTextBrowser` preview.
- Bottom: "To PDF" button + checked count.
- Reorder dialog: `QDialog` with `QListWidget` + Up/Down buttons + OK/Cancel.

### Files
| File | Action |
|---|---|
| `modules/codex/project_screen.py` | Full rewrite |
| `modules/codex/gui_screen.py` | Full rewrite |
| `modules/codex/module.toml` | Update description; remove vault setup fields |
| `modules/codex/setup_screen.py` | Delete |

---

## Part 3: Apply to Existing Projects

After code changes: call `ensure_module_dirs` for each active module across all 5 existing projects. Create `codex/` output dir for projects with Codex active.

---

## Sequence

1. ✅ Plan.md rewritten
2. `nexus/core/project_manager.py` — `ensure_module_dirs`, path helpers, `ProjectInfo.path`
3. `nexus/ui/tui/project_hub_screen.py` — wire `ensure_module_dirs` into ModuleSelectorModal
4. `nexus/ui/tui/base_project_screen.py` — path field + move-confirmation in EditProjectModal
5. `nexus/ui/gui/project_hub_widget.py` — Config button + dialog + setup-wizard check
6. `modules/codex/` — rewrite TUI, GUI, toml; delete setup_screen
7. Existing 5 projects — apply `ensure_module_dirs`
