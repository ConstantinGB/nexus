from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Header, Footer, TabbedContent, TabPane,
    ListView, ListItem, Label, Input, Button, Static,
)
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.reactive import reactive

from nexus.ai.mcp_registry import REGISTRY, MCPServerSpec
from nexus.core.config_manager import (
    load_global_config,
    add_global_mcp_server,
    remove_global_mcp_server,
    merged_mcp_servers,
)


class ServerRow(ListItem):
    DEFAULT_CSS = """
    ServerRow {
        padding: 0 2;
        height: 3;
        background: #2D1B4E;
        border-bottom: solid #3A2260;
    }
    ServerRow:hover { background: #3A2260; }
    ServerRow .row-name { color: #E0E0FF; text-style: bold; }
    ServerRow .row-tag  { color: #00B4FF; }
    ServerRow .row-status-ok  { color: #00FF88; }
    ServerRow .row-status-off { color: #555555; }
    """

    def __init__(self, spec: MCPServerSpec, active: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.spec = spec
        self.active = active

    def compose(self) -> ComposeResult:
        status = "[active]" if self.active else "[inactive]"
        status_class = "row-status-ok" if self.active else "row-status-off"
        tags = "  ".join(self.spec.tags)
        with Horizontal():
            yield Label(self.spec.name, classes="row-name")
            yield Label(f"  {tags}", classes="row-tag")
            yield Label(f"  {status}", classes=status_class)


class ServerConfigForm(Vertical):
    DEFAULT_CSS = """
    ServerConfigForm {
        background: #1A0A2E;
        border: solid #00B4FF;
        padding: 1 2;
        margin: 1;
        height: auto;
    }
    ServerConfigForm .form-title   { color: #00B4FF; text-style: bold; margin-bottom: 1; }
    ServerConfigForm .form-desc    { color: #A0A0CC; margin-bottom: 1; }
    ServerConfigForm .env-label    { color: #00FF88; }
    ServerConfigForm Input         { margin-bottom: 1; }
    ServerConfigForm .form-buttons { margin-top: 1; height: 3; }
    """

    def __init__(self, spec: MCPServerSpec, **kwargs):
        super().__init__(**kwargs)
        self.spec = spec

    def compose(self) -> ComposeResult:
        yield Label(self.spec.name, classes="form-title")
        yield Label(self.spec.description, classes="form-desc")
        if self.spec.required_env:
            for env_key in self.spec.required_env:
                yield Label(env_key, classes="env-label")
                yield Input(placeholder=f"Enter {env_key}", id=f"env_{env_key}", password="KEY" in env_key or "TOKEN" in env_key or "SECRET" in env_key)
        else:
            yield Label("No credentials required.", classes="form-desc")
        with Horizontal(classes="form-buttons"):
            yield Button("Add Server", id="btn_add", variant="success")
            yield Button("Cancel", id="btn_cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel":
            self.remove()
            return
        if event.button.id == "btn_add":
            cfg = self.spec.default_config()
            for env_key in self.spec.required_env:
                input_widget = self.query_one(f"#env_{env_key}", Input)
                cfg["env"][env_key] = input_widget.value
            add_global_mcp_server(self.spec.id, cfg)
            self.app.notify(f"{self.spec.name} added!", severity="information")
            self.remove()
            self.app.query_one(MCPScreen).refresh_active()


class MCPScreen(Screen):
    BINDINGS = [("escape", "dismiss", "Back")]

    DEFAULT_CSS = """
    MCPScreen {
        background: #1A0A2E;
    }
    MCPScreen Header { background: #2D1B4E; color: #00B4FF; }
    MCPScreen Footer { background: #2D1B4E; color: #00FF88; }

    MCPScreen TabbedContent { height: 1fr; }

    MCPScreen .tab-hint {
        color: #666699;
        padding: 1 2;
        height: 3;
    }
    MCPScreen .empty-label {
        color: #555588;
        padding: 2 4;
    }
    MCPScreen .section-title {
        color: #00B4FF;
        text-style: bold;
        padding: 0 2;
        height: 2;
    }
    MCPScreen ListView { height: 1fr; background: #1A0A2E; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent("Active Servers", "Add Servers"):
            with TabPane("Active Servers", id="tab_active"):
                yield Label("Servers currently configured in settings.yaml.", classes="tab-hint")
                yield ListView(id="active_list")
            with TabPane("Add Servers", id="tab_available"):
                yield Label("Click a server to configure and add it.", classes="tab-hint")
                yield ScrollableContainer(
                    *[ServerRow(spec, active=False, id=f"avail_{spec.id}") for spec in REGISTRY],
                    id="available_list",
                )
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_active()

    def refresh_active(self) -> None:
        active_servers = merged_mcp_servers()
        lv = self.query_one("#active_list", ListView)
        lv.clear()
        if not active_servers:
            lv.append(ListItem(Label("No servers configured yet. Go to 'Add Servers'.", classes="empty-label")))
            return
        for server_id, cfg in active_servers.items():
            lv.append(ListItem(Label(f"  {server_id}  —  {cfg.get('command', '')} {' '.join(cfg.get('args', [])[:2])}…", classes="section-title")))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # Remove button for active servers
        pass

    def on_list_item_highlighted(self, event) -> None:
        pass

    def on_click(self, event) -> None:
        # Handle clicks on available server rows
        for node in event.path:
            if isinstance(node, ServerRow):
                self._show_config_form(node.spec)
                break

    def _show_config_form(self, spec: MCPServerSpec) -> None:
        # Remove any existing form
        for form in self.query(ServerConfigForm):
            form.remove()
        active_pane = self.query_one("#tab_available")
        active_pane.mount(ServerConfigForm(spec))
