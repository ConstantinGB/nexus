from __future__ import annotations
import asyncio
from pathlib import Path

import yaml
from textual.app import ComposeResult
from textual.widgets import Label, Button, Log
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.core.config_manager import load_project_config, save_project_config
from nexus.ui.base_project_screen import BaseProjectScreen, InputModal, _screen_css

log = get("server.project_screen")

_PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"


class _AddServiceModal(InputModal):
    """Two-field modal for adding a service."""

    DEFAULT_CSS = InputModal.DEFAULT_CSS + """
    #im-port  { margin-bottom: 0; }
    #im-type  { margin-bottom: 1; }
    #im-type-label { color: #00FF88; height: 1; margin-top: 1; }
    """

    def compose(self) -> ComposeResult:
        from textual.widgets import Input as _Input, Label as _Label
        from textual.containers import Vertical as _Vert, Horizontal as _Horiz
        with _Vert(id="im-dialog"):
            yield _Label("Add Service", id="im-title")
            yield _Label("Service name (e.g. jellyfin):", id="im-prompt")
            yield _Input(placeholder="jellyfin", id="im-input")
            yield _Label("Port:", classes="im-type-label")
            yield _Input(placeholder="8096", id="im-port")
            yield _Label("Type (systemd / docker):", classes="im-type-label")
            yield _Input(placeholder="docker", id="im-type")
            with _Horiz(id="im-btns"):
                yield Button("Add", id="im-ok", variant="primary")
                yield Button("Cancel", id="im-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "im-ok":
            name = self.query_one("#im-input").value.strip()
            port = self.query_one("#im-port").value.strip()
            svc_type = self.query_one("#im-type").value.strip() or "docker"
            if name:
                self.dismiss({"name": name, "port": port, "type": svc_type})
            else:
                self.dismiss(None)
        else:
            self.dismiss(None)


class ServiceRow(Horizontal):
    """One row per service in the server dashboard."""

    DEFAULT_CSS = """
    ServiceRow { height: 3; padding: 0 1; border-bottom: solid #3A2260; }
    .svc-name   { color: #E0E0FF; width: 18; content-align: left middle; }
    .svc-port   { color: #8080AA; width: 8;  content-align: left middle; }
    .svc-type   { color: #8080AA; width: 10; content-align: left middle; }
    .svc-status { width: 12; content-align: left middle; }
    ServiceRow Button { min-width: 7; margin-right: 1; }
    """

    def __init__(self, service: dict) -> None:
        self._service = service
        name = service.get("name", "?")
        super().__init__(id=f"svc-row-{name}")

    def compose(self) -> ComposeResult:
        name     = self._service.get("name", "?")
        port     = self._service.get("port", "—")
        svc_type = self._service.get("type", "?")
        yield Label(name,     classes="svc-name")
        yield Label(f":{port}", classes="svc-port")
        yield Label(svc_type, classes="svc-type")
        yield Label("…",      id=f"svc-status-{name}", classes="svc-status")
        yield Button("Start",  id=f"svc-start-{name}")
        yield Button("Stop",   id=f"svc-stop-{name}")
        yield Button("Logs",   id=f"svc-logs-{name}")


class ServerProjectScreen(BaseProjectScreen):
    MODULE_KEY   = "server"
    MODULE_LABEL = "SERVER"
    SETUP_FIELDS = [
        {"id": "docker_compose_dir", "label": "Docker Compose directory (optional)",
         "placeholder": "~/server/compose", "optional": True},
    ]

    DEFAULT_CSS = _screen_css("ServerProjectScreen") + ServiceRow.DEFAULT_CSS

    # ── Action buttons ────────────────────────────────────────────────────────

    def _compose_action_buttons(self) -> list:
        return [
            Button("Add Service",   id="btn-add-service", variant="primary"),
            Button("Refresh All",   id="btn-refresh"),
            Button("Docker PS",     id="btn-docker-ps"),
        ]

    # ── Main content ──────────────────────────────────────────────────────────

    async def _populate_content(self) -> None:
        area = self.query_one("#content-area", Vertical)
        await area.remove_children()

        services = self._mod.get("services", [])

        if not services:
            await area.mount(
                Label("No services configured yet.", classes="hint"),
                Label("Click 'Add Service' to register a service.", classes="hint"),
            )
            return

        rows = [ServiceRow(svc) for svc in services]
        await area.mount(*rows)

        # Poll status concurrently
        await asyncio.gather(*[self._poll_status(svc) for svc in services])

    async def _poll_status(self, service: dict) -> None:
        name     = service.get("name", "")
        svc_type = service.get("type", "docker")
        status   = "unknown"
        try:
            if svc_type == "systemd":
                proc = await asyncio.create_subprocess_exec(
                    "systemctl", "is-active", name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                out, _ = await proc.communicate()
                status = out.decode().strip()
            else:
                proc = await asyncio.create_subprocess_exec(
                    "docker", "inspect", "--format={{.State.Status}}", name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                out, _ = await proc.communicate()
                status = out.decode().strip() or "not found"
        except FileNotFoundError:
            status = "cmd missing"
        except Exception:
            log.exception("Status poll failed for %s", name)
            status = "error"

        try:
            lbl = self.query_one(f"#svc-status-{name}", Label)
            color = "status-ok" if status in ("active", "running") else "status-err"
            lbl.update(status)
            lbl.remove_class("status-ok", "status-err")
            lbl.add_class(color)
        except Exception:
            pass

    # ── Button handler ────────────────────────────────────────────────────────

    def _handle_action(self, bid: str | None) -> None:
        if bid == "btn-add-service":
            self.app.push_screen(_AddServiceModal("", ""), self._on_service_added)

        elif bid == "btn-refresh":
            self.run_worker(self._populate_content())

        elif bid == "btn-docker-ps":
            self.run_worker(self._run_cmd(["docker", "ps"]))

        elif bid and bid.startswith("svc-start-"):
            name = bid[len("svc-start-"):]
            self._service_action("start", name)

        elif bid and bid.startswith("svc-stop-"):
            name = bid[len("svc-stop-"):]
            self._service_action("stop", name)

        elif bid and bid.startswith("svc-logs-"):
            name = bid[len("svc-logs-"):]
            self._service_logs(name)

    def _on_service_added(self, result: dict | None) -> None:
        if not result:
            return
        services = list(self._mod.get("services", []))
        services.append(result)
        self._mod["services"] = services
        self._cfg[self.MODULE_KEY] = self._mod
        save_project_config(self.project.slug, self._cfg)
        self.app.notify(f"Service '{result['name']}' added.")
        self.run_worker(self._populate_content())

    def _get_service(self, name: str) -> dict | None:
        for svc in self._mod.get("services", []):
            if svc.get("name") == name:
                return svc
        return None

    def _service_action(self, action: str, name: str) -> None:
        svc = self._get_service(name)
        if not svc:
            return
        svc_type = svc.get("type", "docker")
        if svc_type == "systemd":
            self.run_worker(self._run_cmd(["systemctl", action, name]))
        else:
            if action == "start":
                self.run_worker(self._run_cmd(["docker", "start", name]))
            elif action == "stop":
                self.run_worker(self._run_cmd(["docker", "stop", name]))
            else:
                self.run_worker(self._run_cmd(["docker", "restart", name]))

    def _service_logs(self, name: str) -> None:
        svc = self._get_service(name)
        if not svc:
            return
        svc_type = svc.get("type", "docker")
        if svc_type == "systemd":
            self.run_worker(
                self._run_cmd(["journalctl", "-u", name, "-n", "50", "--no-pager"])
            )
        else:
            self.run_worker(self._run_cmd(["docker", "logs", "--tail", "50", name]))
