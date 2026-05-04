# {project_name}

This is a custom Nexus project. It has its own isolated screen files that you can
freely edit to change how this project looks and behaves — without touching any other
project or the shared module code.

## What is this project?

<!-- Describe your project clearly:
     - What are you building, doing, or learning?
     - What is the end goal?
     - What does "done" look like?
     - Any hard constraints (language, platform, deadline, budget)? -->

## Current state

<!-- What already exists? What have you tried so far?
     Links to repos, files, or docs if relevant. -->

## Tools and technologies

<!-- What languages, frameworks, libraries, or tools are involved?
     e.g. Python + FastAPI, Rust, Bash scripts, Blender, Excel, pen-and-paper -->

---

## Customising this project's UI

Every custom project can have its own full screen implementation. Nexus loads these
files instead of the shared custom module defaults if they exist:

| File                                    | UI            | Required class name   |
| --------------------------------------- | ------------- | --------------------- |
| `projects/{project_slug}/screen.py`     | TUI (Textual) | `ProjectScreen`       |
| `projects/{project_slug}/gui_screen.py` | GUI (PySide6) | `GuiScreen`           |

Recommended base classes: `BaseProjectScreen` (`nexus.ui.tui.base_project_screen`) for TUI;
`ModuleGuiBase` (`nexus.ui.gui.module_base`) for GUI. You may also subclass the existing
custom defaults directly: `modules.custom.project_screen.ProjectScreen` /
`modules.custom.gui_screen.GuiScreen`.

**Rules:**

- The class must be named `ProjectScreen` (TUI) or `GuiScreen` (GUI).
- The active Nexus theme is inherited automatically — accent colours, background, fonts.
- If a file has a syntax error or import failure, Nexus logs the exception and falls back
  to the shared custom screen. The project always opens.
- Changes take effect the next time the project is opened (close and reopen the tab).
- These files are isolated to this project directory. Editing them cannot affect any
  other project.

### TUI skeleton (`screen.py`)

```python
from __future__ import annotations
from modules.custom.project_screen import ProjectScreen as _CustomBase
from nexus.core.project_manager import ProjectInfo


class ProjectScreen(_CustomBase):
    """Per-project TUI screen — extend or replace anything from the base."""

    # Override DEFAULT_CSS to restyle without touching the shared module:
    # DEFAULT_CSS = _CustomBase.DEFAULT_CSS + """
    # #project-title { color: #FF6B35; }
    # """

    def __init__(self, project: ProjectInfo) -> None:
        super().__init__(project)
        # additional setup here
```

### GUI skeleton (`gui_screen.py`)

```python
from __future__ import annotations
from modules.custom.gui_screen import GuiScreen as _CustomBase
from nexus.core.project_manager import ProjectInfo


class GuiScreen(_CustomBase):
    """Per-project GUI screen — extend or replace anything from the base."""

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"{project.name}")
        # additional setup here

    # Override _build_toolbar() to add or replace buttons:
    # def _build_toolbar(self) -> None:
    #     self._add_btn("My Button", self._do_thing, primary=True)
    #     self._add_btn("Open Folder", self._do_open)
```

---

## Skills

| Skill | Inputs | Description |
|-------|--------|-------------|
| `custom_run_command` | `project_slug`, `label` | Run a named shell command defined in this project's config |
| `custom_ask` | `project_slug`, `question` | Ask the AI a question in the context of this project |

## Local Model Guidance

- `custom_ask` is reliable with 7B+ models. Use explicit, self-contained questions.
- `custom_run_command` is purely mechanical — local model quality is irrelevant.
- If the model returns no tool call: re-prompt with "Call the custom_ask tool with question: \<your question\>."

## Notes for the AI

<!-- Anything specific to keep in mind: preferred coding style, things to avoid,
     context about why decisions were made, or relevant background knowledge. -->
