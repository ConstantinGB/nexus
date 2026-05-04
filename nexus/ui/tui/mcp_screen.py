from __future__ import annotations
import shlex

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
    save_global_config,
    add_global_mcp_server,
    remove_global_mcp_server,
    merged_mcp_servers,
)


# ── Catalog row (add-servers tab) ─────────────────────────────────────────────

class ServerRow(ListItem):
    DEFAULT_CSS = """
    ServerRow {
        padding: 0 2;
        height: 3;
        background: $theme-surface;
        border-bottom: solid $theme-border-dim;
    }
    ServerRow:hover { background: $theme-border-dim; }
    ServerRow .row-name { color: $theme-text; text-style: bold; }
    ServerRow .row-tag  { color: $theme-border; }
    ServerRow .row-status-ok  { color: #00FF88; }
    ServerRow .row-status-off { color: $theme-text-dim; }
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


# ── Active server row (active-servers tab) ────────────────────────────────────

class ActiveServerRow(ListItem):
    DEFAULT_CSS = """
    ActiveServerRow {
        padding: 0 2;
        height: 2;
        background: $theme-surface;
        border-bottom: solid $theme-border-dim;
    }
    ActiveServerRow:hover { background: $theme-border-dim; }
    ActiveServerRow.-highlighted { background: $theme-border-dim; }
    ActiveServerRow .srv-id   { color: $theme-text; text-style: bold; }
    ActiveServerRow .srv-cmd  { color: $theme-text-dim; }
    """

    def __init__(self, server_id: str, cfg: dict, **kwargs):
        super().__init__(**kwargs)
        self.server_id = server_id
        self.srv_cfg   = cfg

    def compose(self) -> ComposeResult:
        cmd_preview = f"{self.srv_cfg.get('command', '')} {' '.join(self.srv_cfg.get('args', []))[:40]}"
        with Horizontal():
            yield Label(self.server_id, classes="srv-id")
            yield Label(f"  {cmd_preview}", classes="srv-cmd")


# ── Add-server config form ────────────────────────────────────────────────────

class ServerConfigForm(Vertical):
    DEFAULT_CSS = """
    ServerConfigForm {
        background: $theme-bg;
        border: solid $theme-border;
        padding: 1 2;
        margin: 1;
        height: auto;
    }
    ServerConfigForm .form-title   { color: $theme-border; text-style: bold; margin-bottom: 1; }
    ServerConfigForm .form-desc    { color: $theme-text-dim; margin-bottom: 1; }
    ServerConfigForm .env-label    { color: $theme-accent2; }
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
                yield Input(placeholder=f"Enter {env_key}", id=f"env_{env_key}",
                            password=any(s in env_key for s in ("KEY", "TOKEN", "SECRET")))
        else:
            yield Label("No credentials required.", classes="form-desc")
        with Horizontal(classes="form-buttons"):
            yield Button("Add Server", id="btn_add", variant="success")
            yield Button("Cancel", id="btn_cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
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
            try:
                self.app.query_one(MCPScreen).refresh_active()
            except Exception:
                pass


# ── Active-server edit form ───────────────────────────────────────────────────

class ServerEditForm(Vertical):
    DEFAULT_CSS = """
    ServerEditForm {
        background: $theme-bg;
        border: solid $theme-border;
        padding: 1 2;
        margin: 1;
        height: auto;
    }
    ServerEditForm .form-title  { color: $theme-border; text-style: bold; margin-bottom: 1; }
    ServerEditForm .field-label { color: $theme-accent2; margin-top: 1; }
    ServerEditForm Input        { margin-bottom: 1; }
    ServerEditForm .form-buttons { margin-top: 1; height: 3; }
    ServerEditForm .env-note    { color: $theme-text-dim; margin-bottom: 1; }
    """

    def __init__(self, server_id: str, cfg: dict, **kwargs):
        super().__init__(**kwargs)
        self._server_id = server_id
        self._cfg       = cfg

    def compose(self) -> ComposeResult:
        yield Label(f"Edit: {self._server_id}", classes="form-title")

        yield Label("Command:", classes="field-label")
        yield Input(value=self._cfg.get("command", ""), id="edit_command",
                    placeholder="e.g. npx")

        yield Label("Args (space-separated):", classes="field-label")
        yield Input(value=" ".join(self._cfg.get("args", [])), id="edit_args",
                    placeholder="e.g. -y @modelcontextprotocol/server-sqlite")

        yield Label("Env vars (KEY=value, one per line):", classes="field-label")
        env_lines = "\n".join(f"{k}={v}" for k, v in self._cfg.get("env", {}).items())
        yield Input(value=env_lines, id="edit_env",
                    placeholder="KEY=value  (one per line or leave blank)")
        yield Label("Use  KEY=value  pairs separated by newlines.", classes="env-note")

        with Horizontal(classes="form-buttons"):
            yield Button("Save", id="btn_save", variant="success")
            yield Button("Cancel", id="btn_cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "btn_cancel":
            self.remove()
            return
        if event.button.id == "btn_save":
            command  = self.query_one("#edit_command", Input).value.strip()
            args_raw = self.query_one("#edit_args",   Input).value.strip()
            env_raw  = self.query_one("#edit_env",    Input).value.strip()

            args = shlex.split(args_raw) if args_raw else []
            env: dict[str, str] = {}
            for line in env_raw.splitlines():
                line = line.strip()
                if "=" in line:
                    k, _, v = line.partition("=")
                    if k.strip():
                        env[k.strip()] = v.strip()

            cfg = load_global_config()
            servers = cfg.get("mcp", {}).get("servers", {})
            if self._server_id in servers:
                servers[self._server_id]["command"] = command
                servers[self._server_id]["args"]    = args
                servers[self._server_id]["env"]     = env
                save_global_config(cfg)
                self.app.notify(f"{self._server_id} updated.", severity="information")

            self.remove()
            try:
                self.app.query_one(MCPScreen).refresh_active()
            except Exception:
                pass


# ── Main MCP screen ───────────────────────────────────────────────────────────

class MCPScreen(Screen):
    BINDINGS = [
        ("escape", "dismiss", "Back"),
        ("e", "edit_server", "Edit"),
        ("d", "delete_server", "Delete"),
    ]

    DEFAULT_CSS = """
    MCPScreen {
        background: $theme-bg;
    }
    MCPScreen Header { background: $theme-surface; color: $theme-border; }
    MCPScreen Footer { background: $theme-surface; color: $theme-accent2; }

    MCPScreen TabbedContent { height: 1fr; }

    MCPScreen .tab-hint {
        color: $theme-text-dim;
        padding: 1 2;
        height: 3;
    }
    MCPScreen .summary-bar {
        color: $theme-accent2;
        padding: 0 2;
        height: 2;
        text-style: bold;
    }
    MCPScreen .empty-label {
        color: $theme-text-dim;
        padding: 2 4;
    }
    MCPScreen .section-title {
        color: $theme-border;
        text-style: bold;
        padding: 0 2;
        height: 2;
    }
    MCPScreen #detail_strip {
        background: $theme-surface;
        border-top: solid $theme-border-dim;
        padding: 1 2;
        height: auto;
        max-height: 10;
        display: none;
    }
    MCPScreen #detail_strip.visible { display: block; }
    MCPScreen .detail-key   { color: $theme-accent2; }
    MCPScreen .detail-value { color: $theme-text; }
    MCPScreen ListView { height: 1fr; background: $theme-bg; }
    """

    _selected_server_id: reactive[str | None] = reactive(None)

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent("Active Servers", "Add Servers"):
            with TabPane("Active Servers", id="tab_active"):
                yield Static("", id="summary_bar", classes="summary-bar")
                yield ListView(id="active_list")
                yield Vertical(id="detail_strip")
            with TabPane("Add Servers", id="tab_available"):
                yield Label("Click a server to configure and add it.", classes="tab-hint")
                yield ScrollableContainer(
                    *[ServerRow(spec, active=False, id=f"avail_{spec.id}") for spec in REGISTRY],
                    id="available_list",
                )
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_active()

    # ── Active tab ────────────────────────────────────────────────────────────

    def refresh_active(self) -> None:
        active_servers = merged_mcp_servers()
        n_active  = len(active_servers)
        n_catalog = len(REGISTRY)

        try:
            bar = self.query_one("#summary_bar", Static)
            bar.update(f"Active: {n_active}  |  Catalog: {n_catalog}  |  (e) Edit  (d) Delete")
        except Exception:
            pass

        try:
            lv = self.query_one("#active_list", ListView)
        except Exception:
            return
        lv.clear()
        if not active_servers:
            lv.append(ListItem(Label("No servers configured yet. Go to 'Add Servers'.",
                                     classes="empty-label")))
            return
        for server_id, cfg in active_servers.items():
            lv.append(ActiveServerRow(server_id, cfg, id=f"srv_{server_id}"))

        self._hide_detail()

    def _hide_detail(self) -> None:
        self._selected_server_id = None
        try:
            strip = self.query_one("#detail_strip", Vertical)
            strip.remove_class("visible")
            strip.remove_children()
        except Exception:
            pass

    def _show_detail(self, server_id: str, cfg: dict) -> None:
        self._selected_server_id = server_id
        try:
            strip = self.query_one("#detail_strip", Vertical)
            strip.remove_children()
            env = cfg.get("env", {})
            env_str = "  ".join(f"{k}=…" for k in env) if env else "(none)"
            strip.mount(Label(f"[detail-key]Command:[/]  {cfg.get('command', '')}  "
                              f"[detail-key]Args:[/]  {' '.join(cfg.get('args', []))[:60]}",
                              classes="detail-value"))
            strip.mount(Label(f"[detail-key]Env:[/]  {env_str}", classes="detail-value"))
            strip.add_class("visible")
        except Exception:
            pass

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id != "active_list":
            return
        item = event.item
        if isinstance(item, ActiveServerRow):
            self._show_detail(item.server_id, item.srv_cfg)
        else:
            self._hide_detail()

    # ── Keyboard actions ──────────────────────────────────────────────────────

    def action_edit_server(self) -> None:
        if not self._selected_server_id:
            self.app.notify("Select an active server first.", severity="warning")
            return
        cfg = merged_mcp_servers().get(self._selected_server_id, {})
        for form in self.query(ServerEditForm):
            form.remove()
        try:
            pane = self.query_one("#tab_active")
            pane.mount(ServerEditForm(self._selected_server_id, cfg))
        except Exception:
            pass

    def action_delete_server(self) -> None:
        sid = self._selected_server_id
        if not sid:
            self.app.notify("Select an active server first.", severity="warning")
            return
        remove_global_mcp_server(sid)
        self.app.notify(f"{sid} removed.", severity="information")
        self.refresh_active()

    # ── Catalog tab click ─────────────────────────────────────────────────────

    def on_click(self, event) -> None:
        widget = event.widget
        while widget is not None:
            if isinstance(widget, ServerRow):
                self._show_config_form(widget.spec)
                break
            widget = widget.parent

    def _show_config_form(self, spec: MCPServerSpec) -> None:
        for form in self.query(ServerConfigForm):
            form.remove()
        active_pane = self.query_one("#tab_available")
        active_pane.mount(ServerConfigForm(spec))
