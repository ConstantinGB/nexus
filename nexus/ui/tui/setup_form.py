from __future__ import annotations

from textual.app import ComposeResult
from textual.css.query import NoMatches
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, Button, Input
from textual.containers import Vertical, Horizontal

from nexus.core.project_manager import ProjectInfo


class SetupForm(Widget):
    """Reusable setup form widget for project configuration."""

    class Saved(Message):
        def __init__(self, data: dict) -> None:
            super().__init__()
            self.data = data

    DEFAULT_CSS = """
    SetupForm {
        background: $theme-surface;
        border: solid $theme-border;
        padding: 1 2;
        width: 72;
        height: auto;
    }
    SetupForm #sf-title { color: $theme-border; text-style: bold; height: 2; }
    SetupForm #sf-error { color: #FF4444; height: 1; }
    SetupForm #sf-btns  { height: 3; margin-top: 1; }
    SetupForm .field-label { color: $theme-accent2; height: 1; margin-top: 1; }
    SetupForm .setup-field-row { height: 3; }
    SetupForm .setup-field-row Input { width: 1fr; }
    SetupForm .browse-btn { width: 10; margin-left: 1; }
    """

    def __init__(self, fields: list[dict], project: ProjectInfo, module_key: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._fields = fields
        self._project = project
        self._module_key = module_key

    def compose(self) -> ComposeResult:
        yield Label(f"Configure — {self._project.name}", id="sf-title")
        for field in self._fields:
            yield Label(field["label"], classes="field-label")
            if field.get("type") == "dir":
                with Horizontal(classes="setup-field-row"):
                    yield Input(
                        placeholder=field.get("placeholder", ""),
                        id=f"sf-{field['id']}",
                        password=field.get("password", False),
                    )
                    yield Button("Browse…", id=f"sf-browse-{field['id']}", classes="browse-btn")
            else:
                yield Input(
                    placeholder=field.get("placeholder", ""),
                    id=f"sf-{field['id']}",
                    password=field.get("password", False),
                )
        yield Label("", id="sf-error")
        with Horizontal(id="sf-btns"):
            yield Button("Save", id="sf-save", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id or ""
        if bid == "sf-save":
            self._handle_save()
        elif bid.startswith("sf-browse-"):
            field_id = bid[len("sf-browse-"):]
            from nexus.ui.tui.dir_picker import DirPickerModal
            try:
                inp = self.query_one(f"#sf-{field_id}", Input)
                start = inp.value or "~"
            except NoMatches:
                start = "~"
            self.app.push_screen(
                DirPickerModal(start),
                lambda p, fid=field_id: self._fill_dir(fid, p),
            )

    def _fill_dir(self, field_id: str, path: str | None) -> None:
        if not path:
            return
        try:
            self.query_one(f"#sf-{field_id}", Input).value = path
        except NoMatches:
            pass

    def _handle_save(self) -> None:
        data: dict = {}
        for field in self._fields:
            fid = field["id"]
            try:
                val = self.query_one(f"#sf-{fid}", Input).value.strip()
            except NoMatches:
                val = ""
            if not val and not field.get("optional", False):
                try:
                    self.query_one("#sf-error", Label).update(f"'{field['label']}' is required.")
                except NoMatches:
                    pass
                return
            data[fid] = val
        try:
            self.query_one("#sf-error", Label).update("")
        except NoMatches:
            pass
        self.post_message(self.Saved(data))
