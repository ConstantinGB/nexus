from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Label, Button
from textual.containers import ScrollableContainer, Vertical, Horizontal

from nexus.core.project_manager import ProjectInfo, list_projects
from nexus.core.logger import get

log = get("ui.tiles")

_MODULE_DISPLAY: dict[str, str] = {
    "research":  "Research",
    "journal":   "Journal",
    "codex":     "Codex",
    "git":       "Git",
    "localai":   "Local AI",
    "web":       "Web",
    "game":      "Game",
    "org":       "Org",
    "home":      "Home",
    "streaming": "Streaming",
    "vtube":     "VTube",
    "emulator":  "Emulator",
    "vault":     "Vault",
    "server":    "Server",
    "custom":    "Custom",
    "backup":    "Backup",
    "sdforge":   "SD Forge",
    "security":  "Security",
}


def _display_name(project: ProjectInfo) -> str:
    from nexus.core.module_manager import MODULE_PREFIX
    prefix = MODULE_PREFIX.get(project.module, "")
    if prefix and project.name.lower().startswith(prefix + "-"):
        return project.name[len(prefix) + 1:]
    return project.name


# ── Confirm-delete modal ───────────────────────────────────────────────────────

class ConfirmDeleteModal(ModalScreen):
    DEFAULT_CSS = """
    ConfirmDeleteModal { align: center middle; }
    #modal-box {
        background: #2D1B4E;
        border: solid #FF4444;
        padding: 1 2;
        width: 56;
        height: auto;
    }
    #modal-title  { color: #FF4444; text-style: bold; height: 2; }
    #modal-name   { color: #E0E0FF; height: 1; padding-left: 2; margin-bottom: 1; }
    .modal-hint   { color: #8080AA; height: 1; }
    #modal-btns   { height: 3; margin-top: 1; }
    #modal-btns Button { margin-right: 1; }
    """

    def __init__(self, project_name: str, title: str = "Delete project?",
                 hint: str = "This permanently removes the project and all its files.",
                 confirm_label: str = "Yes, delete"):
        super().__init__()
        self.project_name  = project_name
        self._title        = title
        self._hint         = hint
        self._confirm_label = confirm_label

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-box"):
            yield Label(self._title, id="modal-title")
            yield Label(self.project_name, id="modal-name")
            yield Label(self._hint, classes="modal-hint")
            with Horizontal(id="modal-btns"):
                yield Button(self._confirm_label, id="btn-yes", variant="error")
                yield Button("Cancel",            id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(event.button.id == "btn-yes")


# ── Project tile ──────────────────────────────────────────────────────────────

class ProjectTile(Widget):
    can_focus = True

    DEFAULT_CSS = """
    ProjectTile {
        border: solid #00B4FF;
        padding: 0 2;
        margin: 1;
        height: 7;
        background: #2D1B4E;
    }
    ProjectTile:hover {
        border: solid #00FF88;
        background: #3A2260;
    }
    ProjectTile:focus {
        border: solid #00FF88;
        background: #3A2260;
    }

    ProjectTile #tile-header  { height: 1; }
    ProjectTile .tile-spacer  { width: 1fr; }
    ProjectTile #btn-del      {
        width: 4; height: 1;
        min-width: 4;
        border: none;
        background: transparent;
        color: #555588;
    }
    ProjectTile #btn-del:hover { color: #FF4444; background: transparent; }
    ProjectTile .project-name {
        text-align: center;
        text-style: bold;
        color: #E0E0FF;
        width: 100%;
        height: 2;
        content-align: center middle;
    }
    ProjectTile .module-label {
        text-align: center;
        color: #00B4FF;
        width: 100%;
        height: 1;
    }
    ProjectTile .project-desc {
        text-align: center;
        color: #8080AA;
        width: 100%;
        height: 1;
    }
    """

    def __init__(self, project: ProjectInfo, **kwargs):
        super().__init__(**kwargs)
        self.project = project

    def compose(self) -> ComposeResult:
        with Horizontal(id="tile-header"):
            yield Label("", classes="tile-spacer")
            yield Button("✕", id="btn-del")
        yield Label(_display_name(self.project), classes="project-name")
        yield Label(
            _MODULE_DISPLAY.get(self.project.module, self.project.module.title()),
            classes="module-label",
        )
        if self.project.description:
            yield Label(self.project.description, classes="project-desc")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "btn-del":
            log.debug("Delete requested for project: %s", self.project.slug)
            self.app.push_screen(
                ConfirmDeleteModal(self.project.name),
                self._on_delete_confirmed,
            )

    def _on_delete_confirmed(self, confirmed: bool) -> None:
        if not confirmed:
            return
        log.info("Deleting project: %s", self.project.slug)
        try:
            from nexus.core.project_manager import delete_project
            delete_project(self.project.slug)
            self.app.query_one(TileGrid).refresh_projects()
            self.app.notify(f"'{self.project.name}' deleted.")
        except Exception:
            log.exception("Failed to delete project: %s", self.project.slug)
            self.app.notify(f"Failed to delete '{self.project.name}' — see log.",
                            severity="error")

    def _open(self) -> None:
        self.app.open_project_tab(self.project)

    def on_click(self) -> None:
        self._open()

    def on_key(self, event) -> None:
        if event.key == "enter":
            event.stop()
            self._open()


# ── Add-project tile ──────────────────────────────────────────────────────────

class AddProjectTile(Widget):
    can_focus = True

    DEFAULT_CSS = """
    AddProjectTile {
        border: dashed #00FF88;
        padding: 1 2;
        margin: 1;
        height: 7;
        background: #1A0A2E;
        align: center middle;
    }
    AddProjectTile:hover {
        border: solid #00FF88;
        background: #0A2A1A;
    }
    AddProjectTile:focus {
        border: solid #00FF88;
        background: #0A2A1A;
    }
    AddProjectTile .add-label {
        color: #00FF88;
        text-style: bold;
        width: 100%;
        text-align: center;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("＋  Add Project", classes="add-label")

    def _open(self) -> None:
        from nexus.ui.add_project_screen import AddProjectScreen

        def on_created(project: ProjectInfo | None) -> None:
            if project:
                self.app.query_one(TileGrid).refresh_projects()
                self.app.notify(f"'{project.name}' created!")

        self.app.push_screen(AddProjectScreen(), on_created)

    def on_click(self) -> None:
        self._open()

    def on_key(self, event) -> None:
        if event.key == "enter":
            event.stop()
            self._open()


# ── Settings tile ─────────────────────────────────────────────────────────────

class SettingsTile(Widget):
    can_focus = True

    DEFAULT_CSS = """
    SettingsTile {
        border: dashed #8080AA;
        padding: 1 2;
        margin: 1;
        height: 7;
        background: #1A0A2E;
        align: center middle;
    }
    SettingsTile:hover {
        border: solid #00B4FF;
        background: #1A1A3A;
    }
    SettingsTile:focus {
        border: solid #00B4FF;
        background: #1A1A3A;
    }
    SettingsTile .settings-label {
        color: #8080AA;
        text-style: bold;
        width: 100%;
        text-align: center;
    }
    SettingsTile:hover .settings-label {
        color: #00B4FF;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("⚙  Settings", classes="settings-label")

    def _open(self) -> None:
        from nexus.ui.settings_screen import SettingsScreen
        self.app.push_screen(SettingsScreen())

    def on_click(self) -> None:
        self._open()

    def on_key(self, event) -> None:
        if event.key == "enter":
            event.stop()
            self._open()


# ── Tile grid ─────────────────────────────────────────────────────────────────

class TileGrid(ScrollableContainer):
    BINDINGS = [
        ("up",    "focus_previous", "Up"),
        ("left",  "focus_previous", "Left"),
        ("down",  "focus_next",     "Down"),
        ("right", "focus_next",     "Right"),
    ]

    DEFAULT_CSS = """
    TileGrid {
        layout: grid;
        grid-size: 3;
        grid-rows: 9;
        padding: 1 2;
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        for project in list_projects():
            yield ProjectTile(project)
        yield AddProjectTile()
        yield SettingsTile()

    def refresh_projects(self) -> None:
        for tile in self.query(ProjectTile):
            tile.remove()
        add_tile = self.query_one(AddProjectTile)
        for project in list_projects():
            self.mount(ProjectTile(project), before=add_tile)
