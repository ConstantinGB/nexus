from __future__ import annotations
from pathlib import Path

from textual.widgets import Label, Button, Log
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.ui.base_project_screen import BaseProjectScreen, _screen_css

log = get("home.project_screen")


class HomeProjectScreen(BaseProjectScreen):
    MODULE_KEY   = "home"
    MODULE_LABEL = "HOME ASSISTANT"
    SETUP_FIELDS = [
        {"id": "ha_url",     "label": "Home Assistant URL",
         "placeholder": "http://homeassistant.local:8123"},
        {"id": "config_dir", "label": "HA config directory",
         "placeholder": "~/.homeassistant"},
        {"id": "token",      "label": "Long-lived access token (optional)",
         "placeholder": "eyJ…", "optional": True, "password": True},
    ]

    DEFAULT_CSS = _screen_css("HomeProjectScreen")

    # ── Action buttons ────────────────────────────────────────────────────────

    def _compose_action_buttons(self) -> list:
        token = self._mod.get("token", "")
        return [
            Button("Ping HA",        id="btn-ping"),
            Button("Check API",      id="btn-check-api",    disabled=not token),
            Button("Open Config Dir",id="btn-open-config"),
            Button("Open in Browser",id="btn-open-browser"),
        ]

    # ── Main content ──────────────────────────────────────────────────────────

    async def _populate_content(self) -> None:
        area = self.query_one("#content-area", Vertical)
        await area.remove_children()

        ha_url     = self._mod.get("ha_url", "")
        config_dir = Path(self._mod.get("config_dir", "")).expanduser()

        widgets: list = [
            Horizontal(
                Label("HA URL:", classes="info-key"),
                Label(ha_url,   classes="info-val"),
                classes="info-row",
            ),
            Horizontal(
                Label("Config dir:", classes="info-key"),
                Label(str(config_dir), classes="info-val"),
                classes="info-row",
            ),
            Horizontal(
                Label("Token:", classes="info-key"),
                Label("configured" if self._mod.get("token") else "not set", classes="info-val"),
                classes="info-row",
            ),
        ]

        if config_dir.exists():
            yaml_files = sorted(config_dir.glob("*.yaml"))
            widgets.append(Label("Config files:", classes="section-label"))
            for f in yaml_files:
                widgets.append(Label(f"  {f.name}", classes="hint"))
            if not yaml_files:
                widgets.append(Label("  No .yaml files found in config directory.", classes="hint"))
        else:
            widgets.append(Label(f"Config directory not found: {config_dir}", classes="status-err"))

        await area.mount(*widgets)

    # ── Button handler ────────────────────────────────────────────────────────

    def _handle_action(self, bid: str | None) -> None:
        ha_url     = self._mod.get("ha_url", "")
        config_dir = str(Path(self._mod.get("config_dir", "")).expanduser())
        token      = self._mod.get("token", "")

        if bid == "btn-ping":
            self.run_worker(
                self._run_cmd(["curl", "-sf", "--max-time", "5", ha_url])
            )
        elif bid == "btn-check-api":
            if not token:
                self.app.notify("No token configured.", severity="warning")
                return
            self.run_worker(
                self._run_cmd([
                    "curl", "-sf", "-H", f"Authorization: Bearer {token}",
                    f"{ha_url}/api/",
                ])
            )
        elif bid == "btn-open-config":
            self.run_worker(self._run_cmd(["xdg-open", config_dir]))
        elif bid == "btn-open-browser":
            self.run_worker(self._run_cmd(["xdg-open", ha_url]))
