---
description: Protocol for keeping TUI and GUI in sync — change types, minimum coverage, and checklists
paths:
  - "modules/**"
  - "nexus/ui/**"
---

## Dual-UI Protocol

Every user-visible feature must exist in both the TUI (`project_screen.py`) and the GUI (`gui_screen.py`). A new feature added to one UI without updating the other is a protocol violation. Always update both in the same commit.

---

## Change Types → What Needs Updating

| Change | TUI location | GUI location |
| ------ | ------------ | ------------ |
| New action button | `_compose_action_buttons()` | `QPushButton` in toolbar in `GuiScreen._build_ui()` |
| New config/setup field | `SETUP_FIELDS` list | Setup section in `GuiScreen.__init__` or a settings widget |
| New content section | `_populate_content()` | Central widget section in `GuiScreen._build_ui()` |
| Changed config key | `project_screen.py` config load | `gui_screen.py` config load (they share `load_project_config()`) |
| New skill | `skills.py` only — UI-agnostic | Update `CLAUDE.template.md` only; no UI change |
| Setup wizard step | `setup_screen.py` | Add matching field to `GuiScreen` setup section |
| New module | `project_screen.py` + `setup_screen.py` | `gui_screen.py` at STUB level minimum |
| Bug fix | Whichever UI has the bug | Fix in the other UI too if the same bug exists there |

---

## GUI Screen Levels

| Level | Definition |
| ----- | ---------- |
| **NONE** | Only `BaseProjectWindow` fallback ("no GUI screen" message) |
| **STUB** | `GuiScreen` exists; all action buttons present (may show "Not yet implemented"); config readable; `ChatPanel` if TUI has one |
| **PARTIAL** | All buttons wired with real logic; config editable; output/log display working |
| **FULL** | Complete feature parity with TUI |

**Minimum for any new module: STUB.** NONE is not acceptable for new modules.

---

## New Module Checklist

Complete **all** items in the same commit — do not leave either side pending.

**TUI:**
- [ ] `modules/<id>/project_screen.py` — `ProjectScreen(BaseProjectScreen)` subclass
- [ ] `modules/<id>/setup_screen.py` — if the module requires setup
- [ ] `modules/<id>/skills.py` — skill registrations
- [ ] `modules/<id>/CLAUDE.template.md` — AI context template
- [ ] `modules/<id>/module.toml` — metadata

**GUI (STUB minimum):**
- [ ] `modules/<id>/gui_screen.py` — `GuiScreen(BaseProjectWindow)` with:
  - All action buttons as `QPushButton` (wired or `_not_implemented()` stub)
  - Config fields displayed (read-only at STUB level is acceptable)
  - `ChatPanel` if the TUI screen has a chat panel

**Registry:**
- [ ] `ModuleInfo` entry in `nexus/core/module_manager.py` `_REGISTRY`
- [ ] Skill import in `nexus/app.py` `_register_skills()`
- [ ] Module added to GUI coverage table at the bottom of this file

---

## Existing Feature Change Checklist

When changing an existing module:

1. **New button added to TUI** → add matching `QPushButton` to `gui_screen.py`; wire it or call `self._not_implemented("Button Name")`.
2. **Button removed from TUI** → remove the button from `gui_screen.py`.
3. **New `SETUP_FIELDS` entry** → display the field in `gui_screen.py` (read-only is fine at STUB/PARTIAL).
4. **Config key renamed or added** → update both screens' config loading blocks.
5. **`_populate_content()` restructured** → update the corresponding section in `GuiScreen._build_ui()`.

---

## GUI Screen Skeleton (STUB level)

```python
# modules/<id>/gui_screen.py
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QTextEdit, QMessageBox,
)
from nexus.core.project_manager import ProjectInfo
from nexus.core.config_manager import load_project_config
from nexus.ui.gui.base_project_window import BaseProjectWindow
from nexus.ui.gui.chat_panel import ChatPanel

log = __import__("nexus.core.logger", fromlist=["get"]).get("<id>.gui_screen")


class GuiScreen(BaseProjectWindow):
    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"<ModuleLabel> — {project.name}")
        self._cfg = load_project_config(project.slug)
        self._mod = self._cfg.get("<module_key>", {})
        self._build_ui()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        # Action toolbar
        toolbar = QHBoxLayout()
        btn_foo = QPushButton("Foo")
        btn_foo.clicked.connect(self._do_foo)
        toolbar.addWidget(btn_foo)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Main content split
        splitter = QSplitter(Qt.Horizontal)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        content_layout.addWidget(self._log)
        splitter.addWidget(content)

        self._chat = ChatPanel(
            self.project.slug,
            ["global", "<module_key>"],
            parent=self,
        )
        splitter.addWidget(self._chat)
        splitter.setSizes([600, 400])
        layout.addWidget(splitter)

        self.setCentralWidget(root)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _not_implemented(self, feature: str = "This feature") -> None:
        QMessageBox.information(self, "Not yet implemented",
                                f"{feature} is not yet available in the GUI.\n\n"
                                "Use the TUI:  uv run nexus open <project-name>")

    # ── Actions ───────────────────────────────────────────────────────────────

    def _do_foo(self) -> None:
        self._not_implemented("Foo")
```

---

## Current GUI Coverage

Update this table whenever a module's coverage level changes.

| Module | GUI Level | Notes |
| ------ | --------- | ----- |
| operator | FULL | Calendar tabs, notes, todo, chat, Today's Brief |
| git | PARTIAL | Repo list, pull/push/commit/status, output log, chat |
| research | PARTIAL | Note list, new note, search, delete, chat |
| custom | PARTIAL | Commands from config, CLAUDE.md viewer, open folder |
| web | PARTIAL | Dev/Build/Test/Lint/Install/Stop, script picker, open dir |
| codex | PARTIAL | Note list, new note (file creation), search stub |
| journal | PARTIAL | Entry list, new entry, compile PDF (pandoc), open PDF |
| game | PARTIAL | Launch editor/game, lint, info rows, export stub |
| org | PARTIAL | File list, new plan/diagram/schedule, open dir |
| home | PARTIAL | Ping, check API, open config dir, open browser |
| streaming | PARTIAL | Launch OBS, check logs, list scenes, open config |
| vtube | PARTIAL | Launch runtime, start tracker stub, check camera, open model dir |
| emulator | PARTIAL | System list, launch RetroArch, browse by system, open ROM dir |
| vault | PARTIAL | GPG list, tool availability badges, encrypt/decrypt stubs |
| server | PARTIAL | Service table, docker ps/stats, add service stub |
| backup | PARTIAL | Info rows, run backup, snapshots, check, forget+prune, restore stub |
| sdforge | PARTIAL | Start/stop/webui/test/generate stubs, prompt inputs |
| youtube | PARTIAL | URL input, download video/audio, open dirs |
| security | PARTIAL | Firewall status, VPN up/down, ports, DNS, fail2ban, audit, pubip |
| promptopt | PARTIAL | Mode toggle, prompt input, optimize stub, copy, save stub |
| localai | PARTIAL | Run inference via curl, test endpoint, docker ps |
