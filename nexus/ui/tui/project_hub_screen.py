from __future__ import annotations
import math

from textual.app import ComposeResult
from textual.css.query import NoMatches
from textual.message import Message
from textual.screen import ModalScreen, Screen
from textual.widgets import Header, Footer, Label, Button
from textual.containers import Vertical, Horizontal, ScrollableContainer

from nexus.core.project_manager import ProjectInfo
from nexus.core.logger import get
from nexus.ui.tui.base_project_screen import InputModeModal

log = get("ui.project_hub_screen")


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


class ProjectHubScreen(Screen):
    """Entry point for a project. Shows all active modules as buttons."""

    BINDINGS = [
        ("escape",    "dismiss",   "Home"),
        ("ctrl+tab",  "next_tab",  "Next Tab"),
        ("alt+left",  "prev_tab",  "Prev Tab"),
        ("alt+right", "next_tab",  "Next Tab"),
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

    #hub-module-grid {
        padding: 1 2;
        height: auto;
        layout: grid;
        grid-size: 4;
        grid-rows: 5;
    }
    .hub-mod-btn {
        height: 5; border: solid $theme-border-dim;
        background: $theme-surface;
        color: $theme-text;
        margin: 0;
    }
    .hub-mod-btn:hover {
        border: solid $theme-accent2;
        background: $theme-border-dim;
    }

    #hub-system-section { padding: 1 2; height: auto; }
    #hub-system-label { color: $theme-text-dim; text-style: bold; height: 1; margin-bottom: 1; }

    #hub-bottom {
        height: 3; background: $theme-surface; padding: 0 2;
        border-top: solid $theme-border-dim;
        dock: bottom;
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
            yield Button("⌨", id="hub-btn-input", classes="panel-btn", tooltip="Open input panel")

        feature_mods = [mid for mid in self.project.modules if not is_system_module(mid)]
        system_mods  = [mid for mid in self.project.modules if is_system_module(mid)]

        with Vertical(id="hub-module-grid"):
            for mid in feature_mods:
                info = get_module(mid)
                label = info.name if info else mid.title()
                desc  = (info.description[:60] if info else "")
                yield Button(f"{label}\n{desc}", id=f"hub-mod-{mid}", classes="hub-mod-btn")

        if system_mods:
            with Vertical(id="hub-system-section"):
                yield Label("System tools", id="hub-system-label")
                with Horizontal():
                    for mid in system_mods:
                        info = get_module(mid)
                        label = info.name if info else mid.title()
                        yield Button(label, id=f"hub-mod-{mid}", classes="hub-mod-btn")

        yield Footer()

    def on_mount(self) -> None:
        from nexus.core.module_manager import is_system_module
        n = sum(1 for m in self.project.modules if not is_system_module(m))
        rows = max(1, math.ceil(n / 4))
        try:
            self.query_one("#hub-module-grid").styles.height = rows * 5 + 2
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id or ""
        if bid == "hub-btn-config":
            self.app.push_screen(ModuleSelectorModal(self.project), self._on_modules_updated)
        elif bid == "hub-btn-input":
            self.app.push_screen(InputModeModal(), self._on_input_mode)
        elif bid.startswith("hub-mod-"):
            module_id = bid[len("hub-mod-"):]
            self._open_module(module_id)

    def _open_module(self, module_id: str) -> None:
        from nexus.core.module_manager import (
            get_project_screen_for_module,
            needs_setup_for_module,
            get_setup_screen_for_module,
        )
        # Check if this specific module needs setup
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
        # Hub screen has no persistent terminal — just notify for now
        # (modules handle their own terminals when pushed)
        if mode and mode != "none":
            self.app.notify(f"Open a module first, then use the input button.")

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
