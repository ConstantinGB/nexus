from __future__ import annotations
import asyncio
from pathlib import Path

import httpx
from textual.widgets import Label, Button, Log
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.core.platform import open_path
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

    # ── Before-save hook ──────────────────────────────────────────────────────

    def _on_before_save(self, data: dict) -> dict:
        config_dir = Path(data.get("config_dir", "")).expanduser()
        if config_dir.is_dir() and not (config_dir / "configuration.yaml").exists():
            self.app.notify(
                "configuration.yaml not found in config dir — check the path.",
                severity="warning",
            )
        return {}

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

    def _primary_folder(self) -> Path | None:
        p = Path(self._mod.get("config_dir", "")).expanduser()
        return p if str(p) != "." else None

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
            self.run_worker(self._do_check_api(ha_url, token))
        elif bid == "btn-open-config":
            self.run_worker(self._run_cmd(open_path(config_dir)))
        elif bid == "btn-open-browser":
            self.run_worker(self._run_cmd(open_path(ha_url)))

    async def _do_check_api(self, ha_url: str, token: str) -> None:
        ui_log = self.query_one("#output-log", Log)
        ui_log.write_line(f"$ GET {ha_url}/api/")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(
                    f"{ha_url}/api/",
                    headers={"Authorization": f"Bearer {token}"},
                )
            ui_log.write_line(f"HTTP {r.status_code}")
            ui_log.write_line(r.text[:500] if r.text else "(empty body)")
            ui_log.write_line("✓ Done" if r.status_code == 200 else f"✗ {r.status_code}")
        except httpx.ConnectError:
            ui_log.write_line("✗ Could not connect to Home Assistant.")
        except Exception as exc:
            log.exception("HA API check failed")
            ui_log.write_line(f"✗ {exc}")
