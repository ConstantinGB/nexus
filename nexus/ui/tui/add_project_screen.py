from __future__ import annotations
import math
from textual.app import ComposeResult
from textual.css.query import NoMatches
from textual.message import Message
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Header, Footer, Label, Input, Button
from textual.containers import Vertical, Horizontal, ScrollableContainer

from nexus.core.module_manager import list_feature_modules, list_system_modules, ModuleInfo, MODULE_PREFIX
from nexus.core.project_manager import create_project, list_projects
from nexus.core.logger import get

log = get("ui.add_project_screen")

_COLS   = 4   # columns in the tile grid
_TILE_H = 5   # height of each module tile


class ModuleTile(Widget):
    """A selectable/toggleable module tile."""

    DEFAULT_CSS = """
    ModuleTile {
        border: solid $theme-border-dim;
        padding: 1 1;
        margin: 0;
        height: 5;
        background: $theme-surface;
    }
    ModuleTile:hover {
        border: solid $theme-accent2;
        background: $theme-border-dim;
    }
    ModuleTile .mod-name { color: $theme-text; text-style: bold; height: 1; }
    ModuleTile .mod-desc { color: $theme-text-dim; height: 2; }
    ModuleTile .mod-sel  { color: #00FF88; height: 1; }

    ModuleTile.tile-selected {
        border: solid $theme-accent2;
        background: $theme-border-dim;
    }
    ModuleTile.tile-selected .mod-name { color: $theme-accent2; }

    ModuleTile.custom-tile {
        border: dashed #5A3A7E;
        background: #1C0A34;
    }
    ModuleTile.custom-tile:hover {
        border: solid $theme-accent2;
        background: #2A1050;
    }
    ModuleTile.custom-tile .mod-name { color: #B080FF; }
    ModuleTile.custom-tile .mod-desc { color: #6A50A0; }
    """

    def __init__(self, module: ModuleInfo, selected: bool = False, **kwargs):
        base_cls = "custom-tile" if module.id == "custom" else ""
        if selected:
            base_cls = (base_cls + " tile-selected").strip()
        super().__init__(classes=base_cls, **kwargs)
        self.module = module
        self._selected = selected

    def compose(self) -> ComposeResult:
        yield Label(self.module.name, classes="mod-name")
        yield Label(self.module.description, classes="mod-desc")
        yield Label("Selected" if self._selected else "", classes="mod-sel", id="sel-lbl")

    def on_click(self) -> None:
        self._selected = not self._selected
        if self._selected:
            self.add_class("tile-selected")
        else:
            self.remove_class("tile-selected")
        try:
            self.query_one("#sel-lbl", Label).update("Selected" if self._selected else "")
        except NoMatches:
            pass

    @property
    def is_selected(self) -> bool:
        return self._selected


class AddProjectScreen(Screen):
    BINDINGS = [("escape", "dismiss", "Cancel")]

    DEFAULT_CSS = """
    AddProjectScreen { background: $theme-bg; }
    AddProjectScreen Header { background: $theme-surface; color: $theme-border; }
    AddProjectScreen Footer { background: $theme-surface; color: $theme-accent2; }

    #pick-title { color: $theme-border; text-style: bold; height: 2; padding: 0 2; }
    #pick-hint  { color: $theme-text-dim; height: 1; padding: 0 2; margin-bottom: 1; }

    #tile-scroll { height: 1fr; padding: 0 2; }

    #feature-section-label { color: $theme-accent2; text-style: bold; height: 1; margin-bottom: 1; }
    #system-section-label  { color: $theme-text-dim; text-style: bold; height: 1; margin-top: 1; margin-bottom: 1; }

    #feature-grid {
        layout: grid;
        grid-size: 4;
        grid-rows: 5;
        height: auto;
    }
    #system-grid {
        layout: grid;
        grid-size: 4;
        grid-rows: 5;
        height: auto;
    }

    #btn-next-row {
        height: 3; padding: 0 2; background: $theme-surface;
        border-top: solid $theme-border-dim;
    }
    #btn-next-row Button { margin-right: 1; }

    #step-name  { align: center middle; height: 1fr; }
    #name-box {
        background: $theme-surface;
        border: solid $theme-border;
        padding: 1 2;
        width: 64;
        height: auto;
    }
    #name-box-title { color: $theme-border; text-style: bold; height: 2; }
    #sel-mod-label  { color: $theme-text-dim; height: 1; margin-bottom: 1; }
    .field-label    { color: $theme-accent2; height: 1; margin-top: 1; }
    Input           { margin-bottom: 0; }
    #btn-row        { height: 3; margin-top: 1; }
    #btn-back       { margin-right: 1; }
    """

    def __init__(self):
        super().__init__()
        self._feature_modules = list_feature_modules()
        self._system_modules = list_system_modules()

    def compose(self) -> ComposeResult:
        yield Header()

        with Vertical(id="step-pick"):
            yield Label("Add Project", id="pick-title")
            yield Label("Select one or more modules, then click Next.", id="pick-hint")
            with ScrollableContainer(id="tile-scroll"):
                yield Label("Feature Modules", id="feature-section-label")
                with Vertical(id="feature-grid"):
                    for m in self._feature_modules:
                        yield ModuleTile(m, id=f"tile-{m.id}")
                yield Label("System Tools (optional)", id="system-section-label")
                with Vertical(id="system-grid"):
                    for m in self._system_modules:
                        yield ModuleTile(m, id=f"tile-{m.id}")
            with Horizontal(id="btn-next-row"):
                yield Button("Next →", id="btn-next", variant="primary")
                yield Button("Cancel", id="btn-cancel-pick")

        with Vertical(id="step-name"):
            with Vertical(id="name-box"):
                yield Label("New Project", id="name-box-title")
                yield Label("", id="sel-mod-label")
                yield Label("Project name:", classes="field-label")
                yield Input(
                    placeholder="e.g. My Daily Driver",
                    id="input-name",
                )
                yield Label("Description (optional):", classes="field-label")
                yield Input(placeholder="A short description", id="input-desc")
                with Horizontal(id="btn-row"):
                    yield Button("← Back",         id="btn-back")
                    yield Button("Create Project",  id="btn-create", variant="success")

        yield Footer()

    def on_mount(self) -> None:
        # Size feature grid
        feat_rows = max(1, math.ceil(len(self._feature_modules) / _COLS))
        try:
            self.query_one("#feature-grid").styles.height = feat_rows * _TILE_H
        except NoMatches:
            pass
        # Size system grid
        sys_rows = max(1, math.ceil(len(self._system_modules) / _COLS))
        try:
            self.query_one("#system-grid").styles.height = sys_rows * _TILE_H
        except NoMatches:
            pass
        self.query_one("#step-name").display = False

    def _get_selected_modules(self) -> list[str]:
        selected = []
        for m in self._feature_modules + self._system_modules:
            try:
                tile = self.query_one(f"#tile-{m.id}", ModuleTile)
                if tile.is_selected:
                    selected.append(m.id)
            except NoMatches:
                pass
        return selected

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id in ("input-name", "input-desc"):
            self._create()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id or ""
        if bid == "btn-next":
            selected = self._get_selected_modules()
            if not selected:
                self.app.notify("Please select at least one module.", severity="error")
                return
            self._go_to_step(2, selected)
        elif bid == "btn-cancel-pick":
            self.dismiss(None)
        elif bid == "btn-back":
            self._go_to_step(1, [])
        elif bid == "btn-create":
            self._create()

    def _create(self) -> None:
        import re as _re
        name = self.query_one("#input-name", Input).value.strip()
        desc = self.query_one("#input-desc", Input).value.strip()
        if not name:
            self.app.notify("Please enter a project name.", severity="error")
            return

        selected = self._get_selected_modules()
        if not selected:
            self.app.notify("Please select at least one module.", severity="error")
            return

        # Use the first non-system feature module's prefix, or the first module's prefix
        feature_mods = [m for m in selected if not __import__("nexus.core.module_manager", fromlist=["is_system_module"]).is_system_module(m)]
        first_mod = feature_mods[0] if feature_mods else selected[0]
        prefix = MODULE_PREFIX.get(first_mod, first_mod[:3])
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
            project = create_project(prefixed_name, selected, desc)
            self.dismiss(project)
        except ValueError as exc:
            self.app.notify(str(exc), severity="error")
        except Exception:
            log.exception("Failed to create project")
            self.app.notify("Failed to create project — see log.", severity="error")

    def _go_to_step(self, step: int, selected: list[str]) -> None:
        self.query_one("#step-pick").display = (step == 1)
        self.query_one("#step-name").display = (step == 2)
        if step == 2 and selected:
            from nexus.core.module_manager import get_module
            names = [get_module(m).name if get_module(m) else m for m in selected]
            self.query_one("#sel-mod-label", Label).update(
                f"Modules: {', '.join(names)}"
            )
            self.query_one("#input-name", Input).focus()
