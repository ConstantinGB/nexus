from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, TextArea


class TextEditorScreen(Screen):
    BINDINGS = [
        ("ctrl+s", "save",    "Save"),
        ("escape", "discard", "Discard"),
    ]

    DEFAULT_CSS = """
    TextEditorScreen { background: #1A0A2E; }
    TextEditorScreen Header { background: #2D1B4E; color: #00B4FF; }
    TextEditorScreen Footer { background: #2D1B4E; color: #00FF88; }
    TextEditorScreen TextArea { height: 1fr; }
    """

    def __init__(self, content: str, language: str = "markdown",
                 title: str = "Edit") -> None:
        super().__init__()
        self._content  = content
        self._language = language
        self._title    = title

    def compose(self) -> ComposeResult:
        yield Header()
        yield TextArea(self._content, language=self._language, id="editor",
                       show_line_numbers=True)
        yield Footer()

    def on_mount(self) -> None:
        self.title = self._title
        self.query_one("#editor", TextArea).focus()

    def action_save(self) -> None:
        self.dismiss(self.query_one("#editor", TextArea).text)

    def action_discard(self) -> None:
        self.dismiss(None)
