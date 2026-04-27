from __future__ import annotations

from dataclasses import dataclass, field

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, Button, Log
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get

log = get("ui.docker_screen")


@dataclass
class DockerContainerConfig:
    name: str
    image: str
    ports: dict[str, str] = field(default_factory=dict)
    volumes: dict[str, str] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    extra_args: list[str] = field(default_factory=list)


class DockerManagerScreen(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close")]

    DEFAULT_CSS = """
    DockerManagerScreen { align: center middle; }

    #docker-dialog {
        background: #2D1B4E;
        border: solid #00B4FF;
        padding: 1 2;
        width: 90;
        height: auto;
        max-height: 46;
    }
    #docker-title  { color: #00B4FF; text-style: bold; height: 2; }
    #docker-status { height: 1; }
    #docker-info   { color: #8080AA; height: 1; margin-bottom: 1; }

    .status-running { color: #00FF88; }
    .status-stopped { color: #FF4444; }
    .status-unknown { color: #888888; }

    #docker-btn-row { height: 3; margin-bottom: 1; }
    #docker-btn-row Button { margin-right: 1; }

    #docker-log { height: 22; background: #0A0518; border: solid #3A2260; }
    """

    def __init__(self, title: str, config: DockerContainerConfig) -> None:
        super().__init__()
        self._title   = title
        self._config  = config
        self._pulling = False

    def compose(self) -> ComposeResult:
        with Vertical(id="docker-dialog"):
            yield Label(f"Docker: {self._title}", id="docker-title")
            yield Label("Checking…", id="docker-status", classes="status-unknown")
            yield Label(
                f"Image: {self._config.image}  |  Container: {self._config.name}",
                id="docker-info",
            )
            with Horizontal(id="docker-btn-row"):
                yield Button("Pull Image",   id="btn-docker-pull")
                yield Button("▶ Start",      id="btn-docker-start",  variant="primary")
                yield Button("■ Stop",       id="btn-docker-stop")
                yield Button("Remove",       id="btn-docker-remove")
                yield Button("Refresh Logs", id="btn-docker-logs")
                yield Button("Close",        id="btn-docker-close")
            yield Log(id="docker-log", auto_scroll=True)

    def on_mount(self) -> None:
        self.run_worker(self._refresh_status())
        self.app._docker_containers.add(self._config.name)

    def on_dismiss(self) -> None:
        self.app._docker_containers.discard(self._config.name)

    # ── Status ────────────────────────────────────────────────────────────────

    async def _refresh_status(self) -> None:
        from nexus.core import docker_ops
        status = await docker_ops.container_status(self._config.name)
        self._set_status(status)

    def _set_status(self, status: str) -> None:
        lbl = self.query_one("#docker-status", Label)
        lbl.remove_class("status-running", "status-stopped", "status-unknown")
        if status == "running":
            lbl.update("● RUNNING")
            lbl.add_class("status-running")
        elif status in ("exited", "stopped"):
            lbl.update("● STOPPED")
            lbl.add_class("status-stopped")
        elif status == "not_found":
            lbl.update("○ NOT CREATED")
            lbl.add_class("status-unknown")
        else:
            lbl.update(f"● {status.upper()}")
            lbl.add_class("status-unknown")

    # ── Buttons ───────────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if   bid == "btn-docker-close":  self.dismiss()
        elif bid == "btn-docker-pull":   self.run_worker(self._pull())
        elif bid == "btn-docker-start":  self.run_worker(self._start())
        elif bid == "btn-docker-stop":   self.run_worker(self._stop())
        elif bid == "btn-docker-remove": self.run_worker(self._remove())
        elif bid == "btn-docker-logs":   self.run_worker(self._fetch_logs())

    # ── Workers ───────────────────────────────────────────────────────────────

    async def _pull(self) -> None:
        if self._pulling:
            self.app.notify("Pull already in progress.", severity="warning")
            return
        from nexus.core import docker_ops
        ui_log = self.query_one("#docker-log", Log)
        ui_log.clear()
        ui_log.write_line(f"$ docker pull {self._config.image}")
        if not await docker_ops.is_available():
            ui_log.write_line("✗ Docker daemon not available — is Docker installed and running?")
            return
        self._pulling = True
        try:
            async for line in docker_ops.pull_image(self._config.image):
                ui_log.write_line(line)
            ui_log.write_line("\n✓ Image pulled.")
            self.app.notify("Image pulled successfully.", severity="information")
        except docker_ops.DockerError as exc:
            ui_log.write_line(f"\n✗ {exc}")
            self.app.notify("Pull failed — see log.", severity="error")
        except Exception:
            log.exception("docker pull failed")
            ui_log.write_line("\n✗ Unexpected error — see nexus log.")
        finally:
            self._pulling = False

    async def _start(self) -> None:
        import asyncio as _aio
        from nexus.core import docker_ops
        ui_log = self.query_one("#docker-log", Log)
        c = self._config
        ui_log.clear()
        ports_str = ", ".join(f"{h}:{cn}" for h, cn in c.ports.items())
        ui_log.write_line(
            f"$ docker run -d --name {c.name}"
            + (f" -p {ports_str}" if ports_str else "")
            + (f" {' '.join(c.extra_args)}" if c.extra_args else "")
            + f" {c.image}"
        )
        if not await docker_ops.is_available():
            ui_log.write_line("✗ Docker daemon not available — is Docker installed and running?")
            return
        try:
            await docker_ops.run_container(
                c.name, c.image, c.ports, c.volumes, c.env, c.extra_args,
            )
            # Brief pause to let fast-exit containers fail visibly
            await _aio.sleep(1.5)
            status = await docker_ops.container_status(c.name)
            if status == "running":
                ui_log.write_line("✓ Container started.")
                self.app.notify(f"'{c.name}' started.", severity="information")
            else:
                ui_log.write_line(
                    f"⚠ Container created but exited immediately (status: {status})."
                    " Check logs for details."
                )
                self.app.notify(
                    "Container exited immediately — check Docker log.", severity="warning"
                )
        except docker_ops.DockerError as exc:
            ui_log.write_line(f"\n✗ {exc}")
            self.app.notify("Start failed — see log.", severity="error")
        except Exception:
            log.exception("docker start failed")
            ui_log.write_line("\n✗ Unexpected error — see nexus log.")
        await self._refresh_status()

    async def _stop(self) -> None:
        from nexus.core import docker_ops
        ui_log = self.query_one("#docker-log", Log)
        ui_log.clear()
        ui_log.write_line(f"$ docker stop {self._config.name}")
        try:
            await docker_ops.stop_container(self._config.name)
            ui_log.write_line("✓ Container stopped.")
            self.app.notify(f"'{self._config.name}' stopped.")
        except docker_ops.DockerError as exc:
            ui_log.write_line(f"\n✗ {exc}")
            self.app.notify("Stop failed — see log.", severity="error")
        except Exception:
            log.exception("docker stop failed")
            ui_log.write_line("\n✗ Unexpected error — see nexus log.")
        await self._refresh_status()

    async def _remove(self) -> None:
        from nexus.core import docker_ops
        ui_log = self.query_one("#docker-log", Log)
        ui_log.clear()
        ui_log.write_line(f"$ docker rm -f {self._config.name}")
        try:
            await docker_ops.remove_container(self._config.name)
            ui_log.write_line("✓ Container removed.")
            self.app.notify(f"'{self._config.name}' removed.")
        except docker_ops.DockerError as exc:
            ui_log.write_line(f"\n✗ {exc}")
            self.app.notify("Remove failed — see log.", severity="error")
        except Exception:
            log.exception("docker remove failed")
            ui_log.write_line("\n✗ Unexpected error — see nexus log.")
        await self._refresh_status()

    async def _fetch_logs(self) -> None:
        from nexus.core import docker_ops
        ui_log = self.query_one("#docker-log", Log)
        ui_log.clear()
        ui_log.write_line(f"$ docker logs --tail 100 {self._config.name}")
        try:
            content = await docker_ops.get_logs(self._config.name)
            for line in content.splitlines():
                ui_log.write_line(line)
            ui_log.write_line("── end of log ──")
        except Exception:
            log.exception("docker logs failed")
            ui_log.write_line("✗ Could not fetch logs — see nexus log.")
        await self._refresh_status()
