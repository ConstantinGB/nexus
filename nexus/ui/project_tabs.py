from __future__ import annotations
from pathlib import Path

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Label, Button
from textual.containers import Vertical, Horizontal, ScrollableContainer

from nexus.core.project_manager import ProjectInfo, list_projects
from nexus.core.logger import get

log = get("ui.project_tabs")


class ProjectTabBar(Widget):
    """Thin tab strip shown at the very top of every project screen."""

    DEFAULT_CSS = """
    ProjectTabBar {
        height: 3;
        background: #0E0620;
        border-bottom: solid #3A2260;
        layout: horizontal;
        overflow-x: auto;
        padding: 0 1;
        align: left middle;
    }
    .project-tab {
        height: 3;
        min-width: 14;
        border: solid #3A2260;
        background: #1A0A2E;
        color: #C0C0DD;
        margin-right: 1;
    }
    .project-tab:hover {
        background: #2D1B4E;
        color: #E0E0FF;
    }
    .project-tab.active-tab {
        background: #2D1B4E;
        color: #00B4FF;
        border: solid #00B4FF;
    }
    .tab-add-btn {
        width: 5;
        height: 3;
        border: solid #3A2260;
        background: #1A0A2E;
        color: #00FF88;
    }
    .tab-add-btn:hover {
        background: #1A2E1A;
        border: solid #00FF88;
    }
    """

    def compose(self) -> ComposeResult:
        tabs = getattr(self.app, "_tabs", [])
        active_idx = getattr(self.app, "_active_tab_idx", -1)
        for i, project in enumerate(tabs):
            classes = "project-tab" + (" active-tab" if i == active_idx else "")
            yield Button(project.name, id=f"ptab-{i}", classes=classes)
        yield Button("+", id="ptab-add", classes="tab-add-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id or ""
        if bid == "ptab-add":
            self.app.push_screen(
                ProjectPickerModal(),
                self._on_project_picked,
            )
        elif bid.startswith("ptab-"):
            try:
                idx = int(bid[len("ptab-"):])
                tabs = getattr(self.app, "_tabs", [])
                if 0 <= idx < len(tabs):
                    self.app.switch_to_tab(tabs[idx])
            except (ValueError, AttributeError):
                pass

    def _on_project_picked(self, project: ProjectInfo | None) -> None:
        if project and hasattr(self.app, "switch_to_tab"):
            self.app.switch_to_tab(project)

    async def refresh_tabs(self) -> None:
        """Rebuild tab buttons to reflect current app._tabs."""
        await self.remove_children()
        tabs = getattr(self.app, "_tabs", [])
        active_idx = getattr(self.app, "_active_tab_idx", -1)
        buttons = []
        for i, project in enumerate(tabs):
            classes = "project-tab" + (" active-tab" if i == active_idx else "")
            buttons.append(Button(project.name, id=f"ptab-{i}", classes=classes))
        buttons.append(Button("+", id="ptab-add", classes="tab-add-btn"))
        if buttons:
            await self.mount(*buttons)


class ProjectPickerModal(ModalScreen[ProjectInfo | None]):
    """Quick modal to pick an existing project to open alongside the current one."""

    DEFAULT_CSS = """
    ProjectPickerModal { align: center middle; }
    #ppm-dialog {
        background: #2D1B4E; border: solid #00B4FF;
        padding: 1 2; width: 60; height: 80%;
    }
    #ppm-title   { color: #00B4FF; text-style: bold; height: 2; }
    #ppm-list    { height: 1fr; border: solid #3A2260; padding: 0 1; }
    .ppm-item    { height: 3; width: 1fr; border: none; background: transparent;
                   color: #8080AA; text-align: left; }
    .ppm-item:hover { background: #2D1B4E; color: #E0E0FF; }
    #ppm-cancel  { height: 3; margin-top: 1; }
    """

    def compose(self) -> ComposeResult:
        projects = list_projects()
        with Vertical(id="ppm-dialog"):
            yield Label("Open Project", id="ppm-title")
            with ScrollableContainer(id="ppm-list"):
                for i, p in enumerate(projects):
                    yield Button(
                        f"{p.name}  [{p.module}]",
                        id=f"ppm-proj-{i}",
                        classes="ppm-item",
                    )
            yield Button("Cancel", id="ppm-cancel")

    def on_mount(self) -> None:
        self._projects = list_projects()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id or ""
        if bid == "ppm-cancel":
            self.dismiss(None)
        elif bid.startswith("ppm-proj-"):
            try:
                idx = int(bid[len("ppm-proj-"):])
                if 0 <= idx < len(self._projects):
                    self.dismiss(self._projects[idx])
            except (ValueError, AttributeError):
                self.dismiss(None)
