from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Label
from textual.containers import Vertical, Horizontal


class DirPickerModal(ModalScreen):
    """Modal directory browser. Dismisses with a path string or None on cancel."""

    BINDINGS = [("escape", "dismiss_none", "Cancel")]

    DEFAULT_CSS = """
    DirPickerModal { align: center middle; }
    #dp-dialog {
        background: #2D1B4E; border: solid #00B4FF;
        padding: 1 2; width: 80; height: 30;
    }
    #dp-title   { color: #00B4FF; text-style: bold; height: 2; }
    #dp-current { color: #8080AA; height: 1; margin-bottom: 1; }
    #dp-tree    { height: 1fr; border: solid #3A2260; }
    #dp-btns    { height: 3; margin-top: 1; }
    #dp-btns Button { margin-right: 1; }
    """

    def __init__(self, start: str | Path | None = None) -> None:
        super().__init__()
        self._start = Path(start).expanduser() if start else Path.home()
        self._selected: Path | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="dp-dialog"):
            yield Label("Browse Directory", id="dp-title")
            yield Label(str(self._start), id="dp-current")
            yield DirectoryTree(str(self._start), id="dp-tree")
            with Horizontal(id="dp-btns"):
                yield Button("Select", id="dp-select", variant="primary")
                yield Button("Cancel", id="dp-cancel")

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        self._selected = Path(event.path)
        self.query_one("#dp-current", Label).update(str(self._selected))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "dp-select":
            self.dismiss(str(self._selected) if self._selected else None)
        else:
            self.dismiss(None)

    def action_dismiss_none(self) -> None:
        self.dismiss(None)
