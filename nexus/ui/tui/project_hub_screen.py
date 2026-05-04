from __future__ import annotations

from textual.app import ComposeResult
from textual.css.query import NoMatches
from textual.message import Message
from textual.screen import ModalScreen, Screen
from textual.widget import Widget
from textual.widgets import Header, Footer, Label, Button
from textual.containers import Vertical, Horizontal, ScrollableContainer

from nexus.core.project_manager import ProjectInfo
from nexus.core.logger import get
from nexus.ui.tui.base_project_screen import InputModeModal

log = get("ui.project_hub_screen")


# ── Module tile ───────────────────────────────────────────────────────────────

class ModuleTile(Widget):
    """Single module tile — mirrors ProjectTile visual style."""

    can_focus = True

    DEFAULT_CSS = """
    ModuleTile {
        border: solid $theme-border;
        padding: 0 2;
        margin: 1;
        height: 7;
        background: $theme-surface;
    }
    ModuleTile:hover  { border: solid $theme-accent2; }
    ModuleTile:focus  { border: solid $theme-accent2; }

    ModuleTile .mod-name {
        text-align: center;
        text-style: bold;
        color: $theme-text;
        width: 100%;
        height: 3;
        content-align: center middle;
    }
    ModuleTile .mod-desc {
        text-align: center;
        color: $theme-text-dim;
        width: 100%;
        height: 2;
    }
    ModuleTile.system .mod-name { color: $theme-text-dim; }
    """

    def __init__(self, module_id: str, label: str, desc: str,
                 is_system: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self._module_id = module_id
        self._label = label
        self._desc = desc
        if is_system:
            self.add_class("system")

    def compose(self) -> ComposeResult:
        yield Label(self._label, classes="mod-name")
        yield Label(self._desc[:80] if self._desc else "", classes="mod-desc")

    def on_click(self) -> None:
        self.screen._open_module(self._module_id)  # type: ignore[attr-defined]

    def on_key(self, event) -> None:
        if event.key == "enter":
            event.stop()
            self.screen._open_module(self._module_id)  # type: ignore[attr-defined]


# ── Module selector modal ─────────────────────────────────────────────────────

class ModuleSelectorModal(ModalScreen[list[str] | None]):
    """Toggle which modules are active for a project."""

    DEFAULT_CSS = """
    ModuleSelectorModal { align: center middle; }
    #msm-dialog {
        background: $theme-surface; border: solid $theme-border;
        padding: 1 2; width: 70; height: 80%;
    }
    #msm-title { color: $theme-border; text-style: bold; height: 2; }
    #msm-scroll { height: 1fr; border: solid $theme-border-dim; padding: 0 1; }
    .msm-section-hdr { color: $theme-accent2; text-style: bold; height: 1; margin-top: 1; }
    .msm-item { height: 3; }
    .msm-item-name { color: $theme-text; width: 20; }
    .msm-item-desc { color: $theme-text-dim; width: 1fr; }
    .msm-toggle { width: 10; }
    .selected-yes { color: #00FF88; }
    .selected-no  { color: $theme-text-dim; }
    #msm-btns { height: 3; margin-top: 1; }
    #msm-btns Button { margin-right: 1; }
    """

    def __init__(self, project: ProjectInfo) -> None:
        super().__init__()
        self._project = project
        self._selected: set[str] = set(project.modules)

    def compose(self) -> ComposeResult:
        from nexus.core.module_manager import list_feature_modules, list_system_modules
        with Vertical(id="msm-dialog"):
            yield Label(f"Modules — {self._project.name}", id="msm-title")
            with ScrollableContainer(id="msm-scroll"):
                yield Label("Features", classes="msm-section-hdr")
                for m in list_feature_modules():
                    active = m.id in self._selected
                    with Horizontal(classes="msm-item"):
                        yield Label(m.name, classes="msm-item-name")
                        yield Label(m.description[:50], classes="msm-item-desc")
                        lbl = "On" if active else "Off"
                        cls = "msm-toggle selected-yes" if active else "msm-toggle selected-no"
                        yield Button(lbl, id=f"msm-tog-{m.id}", classes=cls)
                yield Label("System tools", classes="msm-section-hdr")
                for m in list_system_modules():
                    active = m.id in self._selected
                    with Horizontal(classes="msm-item"):
                        yield Label(m.name, classes="msm-item-name")
                        yield Label(m.description[:50], classes="msm-item-desc")
                        lbl = "On" if active else "Off"
                        cls = "msm-toggle selected-yes" if active else "msm-toggle selected-no"
                        yield Button(lbl, id=f"msm-tog-{m.id}", classes=cls)
            with Horizontal(id="msm-btns"):
                yield Button("Save", id="msm-save", variant="primary")
                yield Button("Cancel", id="msm-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id or ""
        if bid == "msm-cancel":
            self.dismiss(None)
        elif bid == "msm-save":
            self.dismiss(sorted(self._selected))
        elif bid.startswith("msm-tog-"):
            mid = bid[len("msm-tog-"):]
            if mid in self._selected:
                self._selected.discard(mid)
                event.button.label = "Off"
                event.button.remove_class("selected-yes")
                event.button.add_class("selected-no")
            else:
                self._selected.add(mid)
                event.button.label = "On"
                event.button.remove_class("selected-no")
                event.button.add_class("selected-yes")


# ── Project hub screen ────────────────────────────────────────────────────────

class ProjectHubScreen(Screen):
    """Entry point for a project — shows all active modules as tiles."""

    BINDINGS = [
        ("escape",    "dismiss",  "Home"),
        ("ctrl+tab",  "next_tab", "Next Tab"),
        ("alt+left",  "prev_tab", "Prev Tab"),
        ("alt+right", "next_tab", "Next Tab"),
    ]

    DEFAULT_CSS = """
    ProjectHubScreen { background: $theme-bg; }
    ProjectHubScreen Header { background: $theme-surface; color: $theme-border; }
    ProjectHubScreen Footer { background: $theme-surface; color: $theme-accent2; }

    #hub-top {
        height: 3; background: $theme-surface; padding: 0 2;
        border-bottom: solid $theme-border-dim;
    }
    #hub-project-name { color: $theme-border; text-style: bold; width: 1fr; }
    #hub-project-desc { color: $theme-text-dim; }

    #hub-tile-grid {
        layout: grid;
        grid-size: 3;
        grid-rows: 9;
        padding: 1 2;
        height: 1fr;
    }
    .hub-section-label {
        column-span: 3;
        color: $theme-text-dim;
        text-style: bold;
        height: 1;
        padding: 0 1;
        margin-top: 1;
    }
    """

    def __init__(self, project: ProjectInfo) -> None:
        super().__init__()
        self.project = project

    def compose(self) -> ComposeResult:
        from nexus.ui.tui.project_tabs import ProjectTabBar
        from nexus.core.module_manager import get_module, is_system_module
        yield Header()
        yield ProjectTabBar()
        with Horizontal(id="hub-top"):
            yield Label(self.project.name, id="hub-project-name")
            if self.project.description:
                yield Label(self.project.description, id="hub-project-desc")
            yield Button("Config", id="hub-btn-config", tooltip="Manage active modules")
            yield Button("⌨", id="hub-btn-input", classes="panel-btn",
                         tooltip="Open input panel")

        feature_mods = [m for m in self.project.modules if not is_system_module(m)]
        system_mods  = [m for m in self.project.modules if is_system_module(m)]

        with ScrollableContainer(id="hub-tile-grid"):
            for mid in feature_mods:
                info = get_module(mid)
                yield ModuleTile(
                    mid,
                    info.name if info else mid.title(),
                    info.description if info else "",
                    id=f"hub-mod-{mid}",
                )
            if system_mods:
                yield Label("System Tools", classes="hub-section-label")
                for mid in system_mods:
                    info = get_module(mid)
                    yield ModuleTile(
                        mid,
                        info.name if info else mid.title(),
                        info.description if info else "",
                        is_system=True,
                        id=f"hub-mod-{mid}",
                    )

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id or ""
        if bid == "hub-btn-config":
            self.app.push_screen(ModuleSelectorModal(self.project), self._on_modules_updated)
        elif bid == "hub-btn-input":
            self.app.push_screen(InputModeModal(), self._on_input_mode)

    def _open_module(self, module_id: str) -> None:
        from nexus.core.module_manager import (
            get_project_screen_for_module,
            needs_setup_for_module,
            get_setup_screen_for_module,
        )
        if needs_setup_for_module(self.project, module_id):
            screen = get_setup_screen_for_module(self.project, module_id)
            if screen:
                self.app.push_screen(screen)
            return
        screen = get_project_screen_for_module(self.project, module_id)
        if screen:
            self.app.push_screen(screen)
        else:
            self.app.notify(f"No screen available for '{module_id}'.", severity="warning")

    def _on_modules_updated(self, modules: list[str] | None) -> None:
        if modules is None:
            return
        from nexus.core.config_manager import load_project_config, save_project_config
        cfg = load_project_config(self.project.slug)
        cfg["modules"] = modules
        save_project_config(self.project.slug, cfg)
        self.project.modules[:] = modules
        self.refresh(recompose=True)

    def _on_input_mode(self, mode: str | None) -> None:
        if mode and mode != "none":
            self.app.notify("Open a module first, then use its input button.")

    def action_dismiss(self, result=None) -> None:
        if hasattr(self.app, "close_project_tab"):
            self.app.close_project_tab(self.project.slug)
        self.dismiss(result)

    def action_next_tab(self) -> None:
        if hasattr(self.app, "action_next_tab"):
            self.app.action_next_tab()

    def action_prev_tab(self) -> None:
        if hasattr(self.app, "action_prev_tab"):
            self.app.action_prev_tab()
