from __future__ import annotations
import math
from textual.app import ComposeResult
from textual.message import Message
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Header, Footer, Label, Input, Button
from textual.containers import Vertical, Horizontal

from nexus.core.module_manager import list_modules, ModuleInfo, MODULE_PREFIX
from nexus.core.project_manager import create_project, list_projects
from nexus.core.logger import get

log = get("ui.add_project_screen")

_COLS   = 4   # columns in the tile grid
_TILE_H = 5   # height of each module tile


def _sorted_modules() -> list[ModuleInfo]:
    modules = list_modules()
    return [m for m in modules if m.id != "custom"] + \
           [m for m in modules if m.id == "custom"]


class ModuleTile(Widget):
    class Selected(Message):
        def __init__(self, module: ModuleInfo) -> None:
            super().__init__()
            self.module = module

    DEFAULT_CSS = """
    ModuleTile {
        border: solid #3A2260;
        padding: 1 1;
        margin: 0;
        height: 5;
        background: #2D1B4E;
    }
    ModuleTile:hover {
        border: solid #00FF88;
        background: #3A2260;
    }
    ModuleTile .mod-name { color: #E0E0FF; text-style: bold; height: 1; }
    ModuleTile .mod-desc { color: #8080AA; height: 2; }

    ModuleTile.custom-tile {
        border: dashed #5A3A7E;
        background: #1C0A34;
    }
    ModuleTile.custom-tile:hover {
        border: solid #00FF88;
        background: #2A1050;
    }
    ModuleTile.custom-tile .mod-name { color: #B080FF; }
    ModuleTile.custom-tile .mod-desc { color: #6A50A0; }
    """

    def __init__(self, module: ModuleInfo, **kwargs):
        super().__init__(classes="custom-tile" if module.id == "custom" else "", **kwargs)
        self.module = module

    def compose(self) -> ComposeResult:
        yield Label(self.module.name,        classes="mod-name")
        yield Label(self.module.description, classes="mod-desc")

    def on_click(self) -> None:
        self.post_message(self.Selected(self.module))


class AddProjectScreen(Screen):
    BINDINGS = [("escape", "dismiss", "Cancel")]

    DEFAULT_CSS = """
    AddProjectScreen { background: #1A0A2E; }
    AddProjectScreen Header { background: #2D1B4E; color: #00B4FF; }
    AddProjectScreen Footer { background: #2D1B4E; color: #00FF88; }

    #pick-title { color: #00B4FF; text-style: bold; height: 2; padding: 0 2; }
    #pick-hint  { color: #555588; height: 1; padding: 0 2; margin-bottom: 1; }

    #tile-grid {
        layout: grid;
        grid-size: 4;
        grid-rows: 5;
        padding: 0 2;
    }

    #step-name  { align: center middle; height: 1fr; }
    #name-box {
        background: #2D1B4E;
        border: solid #00B4FF;
        padding: 1 2;
        width: 64;
        height: auto;
    }
    #name-box-title { color: #00B4FF; text-style: bold; height: 2; }
    #sel-mod-label  { color: #8080AA; height: 1; margin-bottom: 1; }
    .field-label    { color: #00FF88; height: 1; margin-top: 1; }
    Input           { margin-bottom: 0; }
    #btn-row        { height: 3; margin-top: 1; }
    #btn-back       { margin-right: 1; }
    """

    def __init__(self):
        super().__init__()
        self._selected_module: ModuleInfo | None = None
        self._modules = _sorted_modules()

    def compose(self) -> ComposeResult:
        yield Header()

        with Vertical(id="step-pick"):
            yield Label("Add Project", id="pick-title")
            yield Label("Click a module type to begin.", id="pick-hint")
            with Vertical(id="tile-grid"):
                for m in self._modules:
                    yield ModuleTile(m)

        with Vertical(id="step-name"):
            with Vertical(id="name-box"):
                yield Label("New Project", id="name-box-title")
                yield Label("", id="sel-mod-label")
                yield Label("Project name:", classes="field-label")
                yield Input(
                    placeholder="e.g. My Repos, Daily Journal, Home Setup",
                    id="input-name",
                )
                yield Label("Description (optional):", classes="field-label")
                yield Input(placeholder="A short description", id="input-desc")
                with Horizontal(id="btn-row"):
                    yield Button("← Back",         id="btn-back")
                    yield Button("Create Project",  id="btn-create", variant="success")

        yield Footer()

    def on_mount(self) -> None:
        rows = math.ceil(len(self._modules) / _COLS)
        self.query_one("#tile-grid").styles.height = rows * _TILE_H
        self.query_one("#step-name").display = False

    def on_module_tile_selected(self, event: ModuleTile.Selected) -> None:
        self._selected_module = event.module
        self._go_to_step(2)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id in ("input-name", "input-desc"):
            self._create()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self._go_to_step(1)
        elif event.button.id == "btn-create":
            self._create()

    def _create(self) -> None:
        name = self.query_one("#input-name", Input).value.strip()
        desc = self.query_one("#input-desc", Input).value.strip()
        if not name:
            self.app.notify("Please enter a project name.", severity="error")
            return
        if not self._selected_module:
            self.app.notify("Please select a module type.", severity="error")
            return
        import re as _re
        mod_id = self._selected_module.id
        prefix = MODULE_PREFIX.get(mod_id, mod_id[:3])
        prefixed_name = f"{prefix}-{name}"
        existing_slugs = {p.slug for p in list_projects()}
        candidate_slug = _re.sub(r"[^a-z0-9-]", "-", prefixed_name.lower().strip())
        candidate_slug = _re.sub(r"-+", "-", candidate_slug).strip("-")
        if candidate_slug in existing_slugs:
            self.app.notify(
                f"A project named '{name}' already exists for this module.",
                severity="error",
            )
            return
        try:
            project = create_project(prefixed_name, mod_id, desc)
            self.dismiss(project)
        except ValueError as exc:
            self.app.notify(str(exc), severity="error")
        except Exception:
            log.exception("Failed to create project")
            self.app.notify("Failed to create project — see log.", severity="error")

    def _go_to_step(self, step: int) -> None:
        self.query_one("#step-pick").display = (step == 1)
        self.query_one("#step-name").display = (step == 2)
        if step == 2 and self._selected_module:
            self.query_one("#sel-mod-label", Label).update(
                f"Module: {self._selected_module.name}"
            )
            self.query_one("#input-name", Input).focus()
