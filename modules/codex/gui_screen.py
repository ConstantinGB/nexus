from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import QListWidget, QInputDialog
from nexus.core.project_manager import ProjectInfo
from nexus.ui.gui.module_base import ModuleGuiBase

log = __import__("nexus.core.logger", fromlist=["get"]).get("codex.gui_screen")


class GuiScreen(ModuleGuiBase):
    SKILL_SCOPES = ["global", "codex"]

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"Codex — {project.name}")
        self._mod = self._cfg.get("codex", {})
        self._refresh()

    def _build_toolbar(self) -> None:
        self._add_btn("New Note",    self._new_note,  primary=True)
        self._add_btn("Search",      self._search)
        self._add_btn("Filter Tags", self._filter)
        self._add_btn("↻ Refresh",   self._refresh)

    def _build_extra(self) -> None:
        self._note_list = QListWidget()
        self._note_list.setMinimumHeight(200)
        self._extra_layout.addWidget(self._note_list)

    def _refresh(self) -> None:
        self._mod = self._cfg.get("codex", {})
        vault_dir = self._mod.get("vault_dir", "")
        self._note_list.clear()
        notes = []
        if vault_dir:
            p = Path(vault_dir).expanduser()
            if p.is_dir():
                notes = sorted(p.glob("**/*.md"))
                for n in notes:
                    self._note_list.addItem(n.stem)
        self._set_info([
            ("Vault dir",   vault_dir or "(not set)"),
            ("Note count",  str(len(notes))),
        ])

    # ── Actions ───────────────────────────────────────────────────────────────

    def _new_note(self) -> None:
        vault_dir = self._mod.get("vault_dir", "")
        if not vault_dir:
            self._append("[error] Vault dir not configured.")
            return
        title, ok = QInputDialog.getText(self, "New Note", "Note title:")
        if not ok or not title.strip():
            return
        path = Path(vault_dir).expanduser() / f"{title.strip()}.md"
        path.write_text(f"# {title.strip()}\n\n")
        self._append(f"[created] {path}")
        self._refresh()

    def _search(self) -> None:
        self._not_implemented("Search notes")

    def _filter(self) -> None:
        self._not_implemented("Filter by tags")
