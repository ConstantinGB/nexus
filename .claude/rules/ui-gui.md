---
description: PySide6 GUI patterns, QThread/asyncio bridge, retrowave theme, and Qt6 quirks
paths:
  - "nexus/ui/gui/**"
  - "modules/*/gui_screen.py"
---

## PySide6 Conventions

Every GUI module screen is a `GuiScreen(BaseProjectWindow)` in `modules/<id>/gui_screen.py`. The main app dispatches via `importlib.import_module(f"modules.{project.module}.gui_screen").GuiScreen`.

`BaseProjectWindow(QMainWindow)` sets: window title, minimum size 960×640, `WA_DeleteOnClose`, status bar with `slug · module`.

## Qt6 Import Quirks

`QAction` lives in `PySide6.QtGui`, **not** `PySide6.QtWidgets`. Always:

```python
from PySide6.QtGui import QAction
```

## AIWorker — QThread/asyncio Bridge

AI calls are blocking and must not run on the Qt main thread. The pattern:

```python
class _AIWorker(QThread):
    response_ready = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, messages, system_prompt, skill_scopes, parent=None):
        super().__init__(parent)
        self._messages = messages
        self._system_prompt = system_prompt
        self._skill_scopes = skill_scopes

    def run(self):
        try:
            from nexus.ai.client import AIClient
            client = AIClient(load_global_config())
            result = asyncio.run(client.chat(
                self._messages,
                system_prompt=self._system_prompt,
                skill_scopes=self._skill_scopes,
            ))
            self.response_ready.emit(result)
        except Exception as exc:
            self.error_occurred.emit(str(exc))
```

Connect signals in the owning widget; store a reference to the worker to prevent GC while running.

## ChatPanel

`nexus/ui/gui/chat_panel.py` — reusable chat widget:

- `ChatPanel(project_slug, skill_scopes, system_prompt, parent)` — reads/writes `projects/<slug>/chat_history.json`
- `submit_message(text: str)` — programmatic send (used by operator "Today's Brief")
- Message bubbles: `[You]` in `#00FF88`, `[AI]` in `#B45AFF`
- Operator chat uses `skill_scopes=["global", "operator"]` for full cross-module access

## Retrowave Theme

Applied to `NexusGuiApp` via `RETROWAVE_THEME` from `nexus/ui/gui/theme.py`. Color palette:

| Role | Hex |
|------|-----|
| Background | `#1A0A2E` |
| Surface | `#2D1B4E` |
| Accent green | `#00FF88` |
| Accent purple | `#B45AFF` |
| Accent magenta | `#FF006E` |
| Accent cyan | `#00D9FF` |
| Dim text | `#664D88` |

Named object selectors: `#primary` on buttons renders with magenta border; `#title` label uses `#00D9FF`; `#dim` uses `#664D88`.

## TileGrid

`nexus/ui/gui/tile_grid.py`:

- `_ProjectTile` — fixed 220×130, module badge (colour-coded), name, description; emits `opened(ProjectInfo)` on click
- `_AddTile` — dashed border; emits `clicked()`
- `TileGrid(QScrollArea)` — `refresh()` rebuilds from `list_projects()`; reflows columns on `resizeEvent`

## Desktop Integration

`.desktop` file: `StartupWMClass=nexus` (PySide6 sets WM_CLASS to `nexus`/`Nexus` via `app.setApplicationName("Nexus")`). Icon at `~/.local/share/icons/hicolor/scalable/apps/nexus.svg`. Run `nexus install-desktop` to regenerate.
