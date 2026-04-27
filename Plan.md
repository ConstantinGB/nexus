# Module Uplifts — Implementation Plan

## Context

This document translates hands-on testing findings into concrete, ordered implementation tasks.
All items are self-contained and can be worked in priority order. Cross-module items apply to
most or all modules; module-specific items are scoped to a single module.

---

## Cross-Module: Directory Handling

### 1.1 — Module Prefix Naming Convention

**Problem:** Two projects from different modules can share the same slug, causing config
collisions and confusion in the `projects/` directory.

**Plan:** Prefix every new project slug with a 3-letter module acronym + `-`:

| Module | Prefix | Example: name "Test" → slug |
|--------|--------|------------------------------|
| research | res | `res-test` |
| journal | jnl | `jnl-test` |
| codex | cod | `cod-test` |
| git | git | `git-test` |
| localai | loc | `loc-test` |
| web | web | `web-test` |
| game | gam | `gam-test` |
| org | org | `org-test` |
| home | hom | `hom-test` |
| streaming | str | `str-test` |
| vtube | vtu | `vtu-test` |
| emulator | emu | `emu-test` |
| vault | vlt | `vlt-test` |
| server | srv | `srv-test` |
| custom | cst | `cst-test` |
| backup | bak | `bak-test` |

**Files:**
- `nexus/core/module_manager.py` — add `MODULE_PREFIX: dict[str, str]` mapping
- `nexus/ui/add_project_screen.py` — prepend prefix to slug before `create_project()` call

**Note:** Existing projects are not renamed. Prefix only applies to newly created projects.

### 1.2 — Duplicate Name Guard

**Problem:** Creating two projects with the same name and module type produces a slug collision.

**Plan:**
- In `add_project_screen.py`, after the user submits a project name: compute the full prefixed
  slug and check `project_manager.list_projects()` for a matching slug.
- Show an inline error label: `"A project named '<name>' already exists for this module."`
- Block the Save/Create action until the name changes.

**Files:** `nexus/ui/add_project_screen.py`

### 1.3 — Default Directories Within `projects/<slug>/`

**Problem:** Default data directories are empty strings — users must type absolute paths. Data
ends up scattered across `~`, not git-ignored, and hard to find.

**Plan:** Change each module's default directory to a sub-path inside the project folder.
Pre-create the subdirectory when the project is first created.

| Module | Config key | Default subdirectory |
|--------|------------|----------------------|
| research | notes_dir | `notes/` |
| codex | vault_dir | `vault/` |
| journal | journal_dir | `journal/` |
| org | output_dir | `plans/` |
| emulator | rom_dir | `roms/` |

`projects/` is already git-ignored; subdirectories inherit that exclusion automatically.

**Files:**
- `nexus/core/project_manager.py:create_project()` — mkdir the subdirectory per module type
- `modules/<id>/setup_screen.py` — update placeholder text to show `<project>/notes/` etc.

### 1.4 — Auto-create Custom Paths

**Problem:** If the user types a custom path that does not exist, the module silently fails
or crashes when trying to list files there.

**Plan:** In each module's setup save handler, after reading the directory Input value:
```python
custom_path = Path(value).expanduser()
if not custom_path.exists():
    custom_path.mkdir(parents=True, exist_ok=True)
    self.app.notify(f"Created: {custom_path}", severity="information")
```

**Files:** All setup screens with directory inputs: research, codex, journal, org, emulator,
game, vault.

### 1.5 — Directory Browse Button

**Problem:** Users must type full directory paths by hand; there is no file system explorer.

**Plan:** Create `nexus/ui/dir_picker.py` — `DirPickerModal(Screen)`:
- Uses Textual's built-in `DirectoryTree` widget (no new dependency).
- Layout: `DirectoryTree` (scrollable) + bottom bar with Select / Cancel buttons.
- Dismisses with the selected path string, or `None` on cancel.

Add `Button("Browse…", id="btn-browse-<field>")` next to each directory `Input` in every
setup screen that has a directory field. On press:
```python
self.app.push_screen(DirPickerModal(), lambda p: self._fill_dir("#field-id", p))
```

**Files:** New `nexus/ui/dir_picker.py`; all setup screens with directory inputs.

---

## Cross-Module: Input Handling

### 2.1 — Enter/Return Submits Forms

**Problem:** Name fields, search boxes, and chat inputs require explicit button clicks; pressing
Enter does nothing.

**Plan:** Handle `on_input_submitted(event: Input.Submitted)` in each affected screen:

| Screen | Input | Action on Enter |
|--------|-------|-----------------|
| `add_project_screen.py` | project name | trigger Save/Create |
| `custom/project_screen.py` | chat input | send message |
| `research/project_screen.py` | search field | run search |
| `codex/project_screen.py` | search field | run search |

Pattern:
```python
def on_input_submitted(self, event: Input.Submitted) -> None:
    if event.input.id == "target-input-id":
        self._do_the_action()
```

**Files:** `nexus/ui/add_project_screen.py`, `modules/custom/project_screen.py`,
`modules/research/project_screen.py`, `modules/codex/project_screen.py`

---

## Cross-Module: Software Auto-detection

### 3.1 — Pre-fill Binary and Config Paths on Setup Mount

**Problem:** Users must manually locate paths to binaries even when already on PATH or in
well-known locations.

**Plan:** In each relevant setup screen's `on_mount`, scan with `shutil.which()` and check
common install paths, then pre-fill Input widgets if found. Only pre-fill if the field is
currently empty (never overwrite a saved value).

| Module | Binary to scan | Field | Extra paths |
|--------|----------------|-------|-------------|
| streaming | `obs`, `obs-studio` | `#obs-bin` | `/snap/bin/obs-studio` |
| streaming | *(config dir)* | `#obs-config-dir` | `~/.config/obs-studio` (Linux), `~/Library/Application Support/obs-studio` (macOS) |
| emulator | `retroarch` | `#retroarch-bin` | `/snap/bin/retroarch` |
| game | `godot4`, `godot` | `#godot-bin` | `/usr/bin/godot4` |

Pattern:
```python
def on_mount(self) -> None:
    binary = shutil.which("obs") or shutil.which("obs-studio")
    inp = self.query_one("#obs-bin", Input)
    if binary and not inp.value:
        inp.value = binary
```

**Files:** `modules/streaming/setup_screen.py`, `modules/emulator/setup_screen.py`,
`modules/game/setup_screen.py`

---

## Research Module

### 4.1 — Editable Note Viewer (Split Pane)

**Problem:** The module creates `.md` files but has no way to view or edit their content
inside the app. Users must open an external editor for every note.

**Plan:** Split `research/project_screen.py` into a two-pane layout:
- **Left pane** (existing): scrollable note list, search bar, action buttons.
- **Right pane** (new): `TextArea(language="markdown")` that loads the selected note.
- On note selection (click filename): read file → `text_area.load_text(content)`.
- Add **Save** button: writes `TextArea.text` back to the file.
- "New Note" prompt → creates file with YAML frontmatter → loads it in the editor.
- Right pane hidden until a note is selected.

**Files:** `modules/research/project_screen.py`

### 4.2 — URL Fetch / Web Capture

**Problem:** There is no in-app mechanism to fetch and save web content as a research note.

**Plan:**
- Add **Fetch URL** button to the Research action bar.
- On press: open `InputModal("Enter URL:")`.
- Fetch via `httpx.AsyncClient` (already a dependency).
- Strip HTML: `re.sub(r'<[^>]+>', '', html)` — no new dependency.
- Save as `.md` note with frontmatter: `source: <url>`, `date: <today>`.
- If AI is configured, offer optional summarise step (non-blocking; falls back to raw text).

**Files:** `modules/research/project_screen.py`

---

## Journal Module

### 5.1 — In-App Entry Editor

**Problem:** "New Entry" creates a dated `.tex` file but provides no way to write content
inside the app.

**Plan:**
- When "New Entry" is pressed: create the file as before (dated LaTeX template), then
  immediately push `TextEditorScreen` (§ 6.1) with the template content pre-loaded.
- On Ctrl+S / Save, write content back to the file.
- "Compile Latest" and "Open PDF" buttons are unaffected.

**Files:** `modules/journal/project_screen.py`

---

## Codex, Journal, Research — Text Editing

### 6.1 — Shared Text Editor Screen

**Problem:** All three text-focused modules need richer editing. Textual's `TextArea`
supports syntax highlighting for Markdown out of the box.

**Plan:** Create `nexus/ui/text_editor_screen.py` — `TextEditorScreen(Screen)`:
```python
class TextEditorScreen(Screen):
    BINDINGS = [("ctrl+s", "save", "Save"), ("escape", "discard", "Discard")]

    def __init__(self, content: str, language: str = "markdown",
                 title: str = "Edit") -> None: ...

    def compose(self) -> ComposeResult:
        yield Header()
        yield TextArea(self._content, language=self._language, id="editor")
        yield Footer()

    def action_save(self) -> None:
        self.dismiss(self.query_one("#editor", TextArea).text)

    def action_discard(self) -> None:
        self.dismiss(None)
```

- `language="markdown"` for Research and Codex notes.
- `language="text"` for Journal LaTeX entries (no built-in LaTeX grammar in Textual).
- Caller pushes screen, receives saved string in callback, writes to disk.

**Files:** New `nexus/ui/text_editor_screen.py`; `modules/journal/project_screen.py`,
`modules/research/project_screen.py`, `modules/codex/project_screen.py`

### 6.2 — Format Preference per Project (Markdown vs LaTeX)

**Problem:** Users want to choose Markdown or LaTeX per project, affecting templates and
AI instructions.

**Plan:**
- Add `format` config field to Research, Codex, and Journal setup screens.
- UI: two `Button` widgets (Markdown / LaTeX) or a `RadioSet` in step 1 of each setup.
- Store as `format: markdown | latex` in `config.yaml`.
- In `project_screen.py`, pass correct `language` to `TextEditorScreen` based on `format`.
- Defaults: Research → `markdown`; Codex → `markdown`; Journal → `latex` (existing behaviour).
- Each module's `CLAUDE.template.md` gets a `## Format` section populated at project creation.

**Files:** `modules/journal/setup_screen.py`, `modules/research/setup_screen.py`,
`modules/codex/setup_screen.py`; their respective `project_screen.py` files.

---

## LocalAI Module

### 7.1 — Catalog Sort: GPU Fit → CPU Only → GPU Tight → Too Large

**Problem:** The model catalog is displayed in insertion order, mixing fit categories randomly.

**Target display order:** ★ GPU fit (recommended) → CPU only (cpu-only) → ~ GPU tight (fits) → ✗ Too large

**Plan:**
```python
_FIT_ORDER = {"recommended": 0, "cpu-only": 1, "fits": 2, "too-large": 3}

# In _rebuild_catalog(), sort before mounting:
hw = self._hw
models_sorted = sorted(
    models,
    key=lambda m: _FIT_ORDER.get(model_catalog.fit_rating(m, hw), 4)
)
for m in models_sorted:
    await container.mount(ModelRow(...))
```

**Files:** `modules/localai/setup_screen.py`, `modules/localai/model_browser_screen.py`

---

## Implementation Priority

| # | Item | Size | Key files |
|---|------|------|-----------|
| 1 | 7.1 Catalog sort | S | localai/setup_screen.py, model_browser_screen.py |
| 2 | 2.1 Enter submits forms | S | add_project_screen.py, custom, research, codex |
| 3 | 3.1 Binary auto-detect | S | streaming, emulator, game setup_screen.py |
| 4 | 6.1 TextEditorScreen | M | new text_editor_screen.py + 3 module screens |
| 5 | 5.1 Journal in-app editor | M | journal/project_screen.py |
| 6 | 4.1 Research split-pane editor | M | research/project_screen.py |
| 7 | 4.2 Research URL fetch | M | research/project_screen.py |
| 8 | 6.2 Format preference | M | 3 setup + 3 project screens |
| 9 | 1.1 Module prefix naming | M | module_manager.py, add_project_screen.py |
| 10 | 1.2 Duplicate name guard | S | add_project_screen.py |
| 11 | 1.3 Default dirs in project folder | M | project_manager.py + setup_screen.py files |
| 12 | 1.4 Auto-create custom paths | S | all setup screens with dir inputs |
| 13 | 1.5 Directory browse button | L | new dir_picker.py + all setup screens |

---

## Verification

```bash
# Syntax check all new/modified files
python -m py_compile \
  nexus/core/module_manager.py \
  nexus/ui/add_project_screen.py \
  nexus/ui/dir_picker.py \
  nexus/ui/text_editor_screen.py \
  modules/localai/setup_screen.py \
  modules/localai/model_browser_screen.py \
  modules/research/project_screen.py \
  modules/journal/project_screen.py \
  modules/codex/project_screen.py \
  modules/streaming/setup_screen.py \
  modules/emulator/setup_screen.py \
  modules/game/setup_screen.py

# Import smoke tests
python -c "from nexus.ui.dir_picker import DirPickerModal; print('dir_picker OK')"
python -c "from nexus.ui.text_editor_screen import TextEditorScreen; print('text_editor OK')"
python -c "from modules.localai.setup_screen import LocalAISetupScreen; print('localai OK')"
python -c "from modules.research.project_screen import ResearchProjectScreen; print('research OK')"

# Manual acceptance tests
# 1. Open LocalAI catalog — GPU fit models appear first, then CPU-only, then GPU tight
# 2. Create a Research project named "Test" → slug is res-test (after prefix work)
# 3. Open Streaming setup — OBS binary field pre-filled if OBS is installed
# 4. Research: click a note → content loads in right-pane TextArea; edit + Save → file updated
# 5. Journal "New Entry" → TextEditorScreen with LaTeX template → Ctrl+S saves file
# 6. Add project screen: type name + press Enter → project created without clicking button
```
