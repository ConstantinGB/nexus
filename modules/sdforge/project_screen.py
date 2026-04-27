from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen, ModalScreen
from textual.widgets import Header, Footer, Label, Button, Input, Log, TextArea, Select
from textual.containers import Vertical, Horizontal, ScrollableContainer

from nexus.core.logger import get
from nexus.core.platform import open_path
from nexus.core.project_manager import ProjectInfo

log = get("sdforge.project_screen")

_PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"


class SDForgeModelBrowserModal(ModalScreen[str | None]):
    BINDINGS = [("escape", "dismiss_none", "Close")]

    DEFAULT_CSS = """
    SDForgeModelBrowserModal {
        align: center middle;
    }
    #mb-dialog {
        background: #2D1B4E;
        border: solid #00B4FF;
        padding: 1 2;
        width: 72;
        height: auto;
        max-height: 30;
    }
    #mb-title  { color: #00B4FF; text-style: bold; height: 2; }
    #mb-status { color: #666699; height: 1; }
    #mb-log    { height: 6; background: #0A0518; border: solid #3A2260; margin-top: 1; }
    #mb-btns   { height: 3; margin-top: 1; }
    #mb-btns Button { margin-right: 1; }
    """

    def __init__(self, project_slug: str, endpoint: str) -> None:
        super().__init__()
        self._slug     = project_slug
        self._endpoint = endpoint.rstrip("/")
        self._models:  list[dict] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="mb-dialog"):
            yield Label("Browse Models", id="mb-title")
            yield Label("Loading…",      id="mb-status")
            yield Select([], id="model-select", prompt="Select a checkpoint…")
            yield Log(id="mb-log", auto_scroll=True)
            with Horizontal(id="mb-btns"):
                yield Button("Set Active Model", id="btn-set-model", variant="primary", disabled=True)
                yield Button("Cancel",           id="btn-mb-cancel")

    def on_mount(self) -> None:
        self.run_worker(self._load_models())

    async def _load_models(self) -> None:
        from modules.sdforge.api_client import list_models, SDForgeAPIError
        mb_log = self.query_one("#mb-log", Log)
        mb_log.write_line(f"$ GET {self._endpoint}/sdapi/v1/sd-models")
        try:
            self._models = await list_models(self._endpoint)
            options = [(m["title"], m["title"]) for m in self._models]
            self.query_one("#model-select", Select).set_options(options)
            self.query_one("#mb-status", Label).update(f"{len(self._models)} checkpoint(s) found")
            self.query_one("#btn-set-model", Button).disabled = False
            mb_log.write_line(f"✓ {len(self._models)} model(s) listed")
        except SDForgeAPIError as exc:
            mb_log.write_line(f"✗ {exc}")
            self.query_one("#mb-status", Label).update("Could not load models — is the server running?")
        except Exception:
            log.exception("Failed to load models in browser")
            mb_log.write_line("✗ Unexpected error — see log.")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-mb-cancel":
            self.dismiss(None)
        elif bid == "btn-set-model":
            sel = self.query_one("#model-select", Select)
            if sel.value and sel.value != Select.BLANK:
                self.run_worker(self._set_model(str(sel.value)))

    async def _set_model(self, title: str) -> None:
        from modules.sdforge.api_client import set_model, SDForgeAPIError
        try:
            mb_log = self.query_one("#mb-log", Log)
        except Exception:
            return  # screen dismissed
        mb_log.write_line(f"Setting model: {title}")
        try:
            self.query_one("#btn-set-model", Button).disabled = True
        except Exception:
            return
        try:
            await set_model(self._endpoint, title)
            try:
                mb_log.write_line("✓ Model activated.")
            except Exception:
                pass
            self.app.notify(f"Model set to '{title}'.", severity="information")

            from nexus.core.config_manager import load_project_config, save_project_config
            cfg = load_project_config(self._slug)
            cfg.setdefault("sdforge", {})["model"] = title
            save_project_config(self._slug, cfg)
        except SDForgeAPIError as exc:
            try:
                mb_log.write_line(f"✗ {exc}")
                self.app.notify(f"Failed to set model: {exc}", severity="error")
                self.query_one("#btn-set-model", Button).disabled = False
            except Exception:
                pass
            return
        except Exception:
            log.exception("Failed to set model")
            try:
                self.query_one("#btn-set-model", Button).disabled = False
            except Exception:
                pass
            return
        self.dismiss(title)

    def action_dismiss_none(self) -> None:
        self.dismiss(None)


class SDForgeProjectScreen(Screen):
    BINDINGS = [("escape", "dismiss", "Back")]

    DEFAULT_CSS = """
    SDForgeProjectScreen { background: #1A0A2E; }
    SDForgeProjectScreen Header { background: #2D1B4E; color: #00B4FF; }
    SDForgeProjectScreen Footer { background: #2D1B4E; color: #00FF88; }

    #top-bar {
        height: 3;
        background: #2D1B4E;
        padding: 0 2;
        border-bottom: solid #3A2260;
    }
    #project-title { color: #00B4FF; text-style: bold; width: 1fr; }
    #project-meta  { color: #8080AA; width: 1fr; }
    #server-status { color: #FF4444; width: 20; content-align: right middle; }
    #server-status.running  { color: #00FF88; }
    #server-status.starting { color: #FFAA00; }

    #action-bar {
        height: 3;
        padding: 0 2;
        background: #241540;
        border-bottom: solid #3A2260;
    }
    #action-bar Button { margin-right: 1; }

    #main-area { height: 1fr; padding: 1 2; overflow-y: auto; }

    .section-label { color: #00B4FF; text-style: bold; height: 1; margin-top: 1; }
    .field-label   { color: #00FF88; height: 1; margin-top: 1; }

    #input-prompt     { height: 5; background: #0A0518; border: solid #3A2260; }
    #input-neg-prompt { height: 3; background: #0A0518; border: solid #3A2260; }

    #param-row { height: 5; margin-top: 1; }
    .param-col { width: 1fr; margin-right: 1; }

    #gen-bar { height: 3; margin-top: 1; margin-bottom: 1; }
    #gen-bar Button { margin-right: 1; }

    #output-log { height: 10; background: #0A0518; border: solid #3A2260; margin-top: 1; }
    """

    def __init__(self, project: ProjectInfo):
        super().__init__()
        self.project           = project
        self._cfg:  dict       = {}
        self._sdf:  dict       = {}
        self._proc: asyncio.subprocess.Process | None = None
        self._server_ready     = asyncio.Event()
        self._last_image_path: Path | None = None

    # ── Config ────────────────────────────────────────────────────────────────

    def _load_cfg(self) -> None:
        from nexus.core.config_manager import load_project_config
        try:
            self._cfg = load_project_config(self.project.slug)
            self._sdf = self._cfg.get("sdforge", {})
        except Exception:
            log.exception("Failed to load config for %s", self.project.slug)
            self._sdf = {}

    # ── Compose ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        self._load_cfg()
        endpoint = self._sdf.get("endpoint", "http://localhost:7860")
        model    = self._sdf.get("model", "")
        meta     = endpoint + (f" · {model}" if model else "")

        yield Header()
        with Horizontal(id="top-bar"):
            yield Label(self.project.name, id="project-title")
            yield Label(meta,              id="project-meta")
            yield Label("● STOPPED",       id="server-status")

        with Horizontal(id="action-bar"):
            yield Button("▶ Start Server", id="btn-start",      variant="primary")
            yield Button("■ Stop Server",  id="btn-stop",       disabled=True)
            yield Button("Open Web UI",    id="btn-open-webui")
            yield Button("Test Endpoint",  id="btn-test")
            yield Button("Browse Models",  id="btn-models")
            yield Button("Docker",         id="btn-docker")

        with Vertical(id="main-area"):
            yield Label("Prompt:", classes="section-label")
            yield TextArea("", id="input-prompt")

            yield Label("Negative Prompt:", classes="field-label")
            yield TextArea("", id="input-neg-prompt")

            with Horizontal(id="param-row"):
                with Vertical(classes="param-col"):
                    yield Label("Width:", classes="field-label")
                    yield Input("512", id="input-width")
                with Vertical(classes="param-col"):
                    yield Label("Height:", classes="field-label")
                    yield Input("512", id="input-height")
                with Vertical(classes="param-col"):
                    yield Label("Steps:", classes="field-label")
                    yield Input("20", id="input-steps")
                with Vertical(classes="param-col"):
                    yield Label("CFG Scale:", classes="field-label")
                    yield Input("7", id="input-cfg")
                with Vertical(classes="param-col"):
                    yield Label("Seed:", classes="field-label")
                    yield Input("-1", id="input-seed")
                with Vertical(classes="param-col"):
                    yield Label("Sampler:", classes="field-label")
                    yield Input("Euler a", id="input-sampler")

            with Horizontal(id="gen-bar"):
                yield Button("Generate",   id="btn-generate",   variant="primary", disabled=True)
                yield Button("Open Image", id="btn-open-image", disabled=True)

            yield Label("Log:", classes="section-label")
            yield Log(id="output-log", auto_scroll=True)

        yield Footer()

    # ── Button handler ────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        try:
            self._handle_button(bid)
        except Exception:
            log.exception("Error in project button handler (button=%s)", bid)
            self.app.notify("Unexpected error — see log.", severity="error")

    def _handle_button(self, bid: str | None) -> None:
        if bid == "btn-start":
            self.run_worker(self._start_server())
        elif bid == "btn-stop":
            self.run_worker(self._stop_server())
        elif bid == "btn-open-webui":
            endpoint = self._sdf.get("endpoint", "http://localhost:7860")
            try:
                subprocess.Popen(open_path(endpoint))
            except Exception:
                log.exception("Failed to open web UI")
                self.app.notify("Could not open browser.", severity="error")
        elif bid == "btn-test":
            self.run_worker(self._test_endpoint())
        elif bid == "btn-models":
            endpoint = self._sdf.get("endpoint", "http://localhost:7860")
            self.app.push_screen(
                SDForgeModelBrowserModal(self.project.slug, endpoint),
                self._on_model_set,
            )
        elif bid == "btn-docker":
            self._open_docker()
        elif bid == "btn-generate":
            self.run_worker(self._generate())
        elif bid == "btn-open-image":
            if self._last_image_path and self._last_image_path.exists():
                try:
                    subprocess.Popen(open_path(self._last_image_path))
                except Exception:
                    log.exception("Failed to open image")
                    self.app.notify("Could not open image.", severity="error")
            else:
                self.app.notify("No image file found.", severity="warning")

    # ── Docker manager ────────────────────────────────────────────────────────

    def _open_docker(self) -> None:
        import re
        import shutil as _shutil
        from nexus.ui.docker_screen import DockerManagerScreen, DockerContainerConfig
        slug  = self.project.slug
        image = self._sdf.get("docker_image", "ghcr.io/lllyasviel/stable-diffusion-webui-forge:latest")
        vram  = self._sdf.get("vram", "none")
        m     = re.search(r"(\d+(?:\.\d+)?)", vram.lower())
        gb    = float(m.group(1)) if m else 0.0
        if gb > 0 and not _shutil.which("nvidia-container-runtime"):
            self.app.notify(
                "--gpus all requested but nvidia-container-toolkit may not be installed"
                " — container start may fail.",
                severity="warning",
            )
        extra = ["--gpus", "all"] if gb > 0 else []
        cfg   = DockerContainerConfig(
            name       = f"nexus-sdforge-{slug}",
            image      = image,
            ports      = {"7860": "7860"},
            extra_args = extra,
        )
        self.app.push_screen(DockerManagerScreen("SD Forge", cfg))

    # ── Server lifecycle ──────────────────────────────────────────────────────

    async def _start_server(self) -> None:
        install_dir  = Path(self._sdf.get("install_dir", "")).expanduser()
        launch_args  = self._sdf.get("launch_args", "--api")
        ui_log       = self.query_one("#output-log", Log)

        if not install_dir or not (install_dir / "webui.sh").exists():
            ui_log.write_line(f"✗ webui.sh not found at {install_dir}")
            self.app.notify("SD Forge not installed — run setup again.", severity="error")
            return

        import shlex as _shlex
        parts = _shlex.split(launch_args) if launch_args.strip() else []
        display_cmd = "bash webui.sh " + launch_args
        ui_log.write_line(f"$ {display_cmd}")
        ui_log.write_line(f"  (cwd: {install_dir})")

        try:
            self._proc = await asyncio.create_subprocess_exec(
                "bash", "webui.sh", *parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(install_dir),
            )
        except Exception as exc:
            log.exception("Failed to launch SD Forge")
            ui_log.write_line(f"✗ Launch failed: {exc}")
            self.app.notify("Failed to start SD Forge — see log.", severity="error")
            return

        self._update_status("starting")
        self.query_one("#btn-start", Button).disabled = True
        self.run_worker(self._stream_server_output())

    async def _stream_server_output(self) -> None:
        proc = self._proc
        if not proc or not proc.stdout:
            return
        ui_log = self.query_one("#output-log", Log)
        ready_signals = ("Running on local URL", "Startup time:", "To create a public link")
        async for raw in proc.stdout:
            line = raw.decode(errors="replace").rstrip()
            ui_log.write_line(line)
            if not self._server_ready.is_set() and any(s in line for s in ready_signals):
                self._server_ready.set()
                self.call_from_thread(self._on_server_ready)
        await proc.wait()
        log.info("SD Forge process exited with code %d", proc.returncode)
        self.call_from_thread(self._on_server_stopped)

    def _on_server_ready(self) -> None:
        self._server_ready.set()
        try:
            self._update_status("running")
            self.query_one("#btn-stop",     Button).disabled = False
            self.query_one("#btn-generate", Button).disabled = False
            self.app.notify("SD Forge is ready.", severity="information")
        except Exception:
            pass  # Screen may have been dismissed

    def _on_server_stopped(self) -> None:
        self._server_ready.clear()
        try:
            self._update_status("stopped")
            self.query_one("#btn-start",    Button).disabled = False
            self.query_one("#btn-stop",     Button).disabled = True
            self.query_one("#btn-generate", Button).disabled = True
        except Exception:
            pass  # Screen may have been dismissed

    def _update_status(self, state: str) -> None:
        lbl = self.query_one("#server-status", Label)
        lbl.remove_class("running", "starting")
        if state == "running":
            lbl.update("● RUNNING")
            lbl.add_class("running")
        elif state == "starting":
            lbl.update("● STARTING…")
            lbl.add_class("starting")
        else:
            lbl.update("● STOPPED")

    async def _stop_server(self) -> None:
        if self._proc and self._proc.returncode is None:
            log.info("Terminating SD Forge process")
            self._proc.terminate()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                log.warning("SD Forge did not stop in time — killing")
                self._proc.kill()
                await self._proc.wait()
        self._proc = None
        self._server_ready.clear()
        # _on_server_stopped is called by _stream_server_output via call_from_thread

    # ── Endpoint test ─────────────────────────────────────────────────────────

    async def _test_endpoint(self) -> None:
        from modules.sdforge.api_client import ping, SDForgeAPIError
        endpoint = self._sdf.get("endpoint", "http://localhost:7860").rstrip("/")
        ui_log   = self.query_one("#output-log", Log)
        ui_log.write_line(f"$ ping {endpoint}/sdapi/v1/progress")
        try:
            ms = await ping(endpoint)
            ui_log.write_line(f"✓ Connected in {ms:.0f}ms")
        except SDForgeAPIError as exc:
            ui_log.write_line(f"✗ {exc}")
        except Exception:
            log.exception("Test endpoint failed")
            ui_log.write_line("✗ Unexpected error — see log.")

    # ── Generate ──────────────────────────────────────────────────────────────

    async def _generate(self) -> None:
        from modules.sdforge.api_client import txt2img, save_image, SDForgeAPIError

        endpoint = self._sdf.get("endpoint", "http://localhost:7860").rstrip("/")
        try:
            ui_log     = self.query_one("#output-log", Log)
            prompt     = self.query_one("#input-prompt",     TextArea).text.strip()
            neg_prompt = self.query_one("#input-neg-prompt", TextArea).text.strip()
        except Exception:
            return  # screen dismissed

        def _int(wid: str, default: int) -> int:
            try:
                return int(self.query_one(wid, Input).value.strip())
            except Exception:
                return default

        def _float(wid: str, default: float) -> float:
            try:
                return float(self.query_one(wid, Input).value.strip())
            except Exception:
                return default

        width   = _int("#input-width",  512)
        height  = _int("#input-height", 512)
        steps   = _int("#input-steps",  20)
        seed    = _int("#input-seed",   -1)
        cfg     = _float("#input-cfg",  7.0)
        sampler = self.query_one("#input-sampler", Input).value.strip() or "Euler a"

        if not prompt:
            self.app.notify("Enter a prompt.", severity="warning")
            return

        try:
            self.query_one("#btn-generate", Button).disabled = True
        except Exception:
            return
        ui_log.write_line(f"Generating: {prompt[:80]}…")

        try:
            images = await txt2img(
                endpoint, prompt, neg_prompt,
                width=width, height=height, steps=steps,
                cfg_scale=cfg, sampler_name=sampler, seed=seed,
            )
        except SDForgeAPIError as exc:
            try:
                ui_log.write_line(f"✗ {exc}")
                self.app.notify(str(exc), severity="error")
                self.query_one("#btn-generate", Button).disabled = False
            except Exception:
                pass
            return
        except Exception:
            log.exception("Generation failed")
            try:
                ui_log.write_line("✗ Unexpected error — see log.")
                self.query_one("#btn-generate", Button).disabled = False
            except Exception:
                pass
            return

        out_dir_rel = self._sdf.get("output_dir", "outputs/")
        output_dir  = _PROJECTS_DIR / self.project.slug / out_dir_rel
        saved = save_image(images[0], output_dir)
        self._last_image_path = saved

        try:
            ui_log.write_line(f"✓ Saved: {saved.name}")
            self.query_one("#btn-generate",   Button).disabled = False
            self.query_one("#btn-open-image", Button).disabled = False
        except Exception:
            pass
        self.app.notify(f"Image saved: {saved.name}", severity="information")

    # ── Model browser callback ────────────────────────────────────────────────

    def _on_model_set(self, model_title: str | None) -> None:
        if not model_title:
            return
        self._load_cfg()
        endpoint = self._sdf.get("endpoint", "http://localhost:7860")
        model    = self._sdf.get("model", "")
        meta     = endpoint + (f" · {model}" if model else "")
        try:
            self.query_one("#project-meta", Label).update(meta)
        except Exception:
            pass

    # ── Dismiss with server cleanup ───────────────────────────────────────────

    def action_dismiss(self, result=None) -> None:
        if self._proc and self._proc.returncode is None:
            self.run_worker(self._stop_and_dismiss(result))
        else:
            super().action_dismiss(result)

    async def _stop_and_dismiss(self, result=None) -> None:
        await self._stop_server()
        self.app.pop_screen()
