from __future__ import annotations
from datetime import date

from textual.app import ComposeResult
from textual.screen import ModalScreen, Screen
from textual.widgets import Label, Button, Input, TextArea
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get

log = get("journal.entry_screen")


class JournalConfigModal(ModalScreen[dict | None]):
    DEFAULT_CSS = """
    JournalConfigModal { align: center middle; }
    #jcm-box {
        background: #2D1B4E; border: solid #00B4FF;
        padding: 1 2; width: 60; height: auto;
    }
    #jcm-title  { color: #00B4FF; text-style: bold; height: 2; }
    .field-label { color: #00FF88; height: 1; margin-top: 1; }
    #jcm-btns   { height: 3; margin-top: 1; }
    #jcm-btns Button { margin-right: 1; }
    """

    def __init__(self, cfg: dict) -> None:
        super().__init__()
        self._cfg = dict(cfg)

    def compose(self) -> ComposeResult:
        with Vertical(id="jcm-box"):
            yield Label("Entry Config", id="jcm-title")
            yield Label("Document class:", classes="field-label")
            yield Input(value=self._cfg.get("documentclass", "article"), id="jcm-docclass")
            yield Label("Paper geometry:", classes="field-label")
            yield Input(value=self._cfg.get("geometry", "a4paper"), id="jcm-geo")
            yield Label("Margin:", classes="field-label")
            yield Input(value=self._cfg.get("margin", "2.5cm"), id="jcm-margin")
            yield Label("Date:", classes="field-label")
            yield Input(value=self._cfg.get("date", str(date.today())), id="jcm-date")
            with Horizontal(id="jcm-btns"):
                yield Button("Apply", id="jcm-apply", variant="primary")
                yield Button("Cancel", id="jcm-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "jcm-apply":
            self.dismiss({
                "documentclass": self.query_one("#jcm-docclass", Input).value.strip() or "article",
                "geometry":      self.query_one("#jcm-geo",      Input).value.strip() or "a4paper",
                "margin":        self.query_one("#jcm-margin",   Input).value.strip() or "2.5cm",
                "date":          self.query_one("#jcm-date",     Input).value.strip() or str(date.today()),
            })
        else:
            self.dismiss(None)


class JournalEntryScreen(Screen[str | None]):
    DEFAULT_CSS = """
    JournalEntryScreen { background: #1A0A2E; }
    #js-top {
        height: 3; background: #2D1B4E;
        border-bottom: solid #3A2260; padding: 0 2;
    }
    #js-top Button { margin-right: 1; }
    #js-body { height: 1fr; }
    """

    BINDINGS = [
        ("ctrl+s", "save",    "Save"),
        ("escape", "discard", "Discard"),
    ]

    def __init__(self, initial_content: str = "", cfg: dict | None = None) -> None:
        super().__init__()
        self._initial_content = initial_content
        self._entry_cfg: dict = cfg or {
            "documentclass": "article",
            "geometry":      "a4paper",
            "margin":        "2.5cm",
            "date":          str(date.today()),
        }

    def compose(self) -> ComposeResult:
        with Horizontal(id="js-top"):
            yield Button("Save",    id="js-save",    variant="primary")
            yield Button("Discard", id="js-discard")
            yield Button("Config",  id="js-config")
        yield TextArea(self._initial_content, id="js-body")

    def on_mount(self) -> None:
        try:
            self.query_one("#js-body", TextArea).focus()
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "js-save":
            self.action_save()
        elif event.button.id == "js-discard":
            self.action_discard()
        elif event.button.id == "js-config":
            self.app.push_screen(JournalConfigModal(self._entry_cfg), self._apply_cfg)

    def _apply_cfg(self, cfg: dict | None) -> None:
        if cfg:
            self._entry_cfg = cfg

    def action_save(self) -> None:
        try:
            text = self.query_one("#js-body", TextArea).text
        except Exception:
            text = ""
        self.dismiss(text)

    def action_discard(self) -> None:
        self.dismiss(None)
