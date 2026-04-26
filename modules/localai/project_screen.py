from __future__ import annotations
import asyncio
import subprocess
from pathlib import Path

import yaml
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Label, Button, Log, TextArea
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.core.platform import open_path
from nexus.core.project_manager import ProjectInfo

log = get("localai.project_screen")

_PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"


class LocalAIProjectScreen(Screen):
    BINDINGS = [("escape", "dismiss", "Back")]

    DEFAULT_CSS = """
    LocalAIProjectScreen { background: #1A0A2E; }
    LocalAIProjectScreen Header { background: #2D1B4E; color: #00B4FF; }
    LocalAIProjectScreen Footer { background: #2D1B4E; color: #00FF88; }

    #top-bar {
        height: 3;
        background: #2D1B4E;
        padding: 0 2;
        border-bottom: solid #3A2260;
    }
    #project-title { color: #00B4FF; text-style: bold; width: 1fr; }
    #project-meta  { color: #8080AA; }

    #main-area { height: 1fr; padding: 1 2; }

    .section-label { color: #00FF88; height: 1; margin-top: 1; }
    .hint          { color: #555588; height: 1; }

    #prompt-input  { height: 6; margin-bottom: 1; }
    #neg-input     { height: 4; margin-bottom: 1; }

    #action-bar    { height: 3; margin-top: 1; margin-bottom: 1; }
    #action-bar Button { margin-right: 1; }
    #btn-open      { border: solid #00B4FF; color: #00B4FF; }

    #output-label  { color: #00FF88; height: 1; margin-top: 1; }
    #output-log    { height: 1fr; background: #0A0518; border: solid #3A2260; }

    #no-setup-banner {
        background: #2A1500;
        border: solid #FFAA00;
        color: #FFAA00;
        padding: 1 2;
        height: auto;
        margin: 2 4;
    }
    """

    def __init__(self, project: ProjectInfo):
        super().__init__()
        self.project      = project
        self._localai_cfg: dict = {}
        self._output_type = "text"
        self._run_command = ""
        self._output_dir  = Path("outputs")
        self._last_output_file: Path | None = None

    # ── Config loading ────────────────────────────────────────────────────────

    def _load_cfg(self) -> None:
        cfg_path = _PROJECTS_DIR / self.project.slug / "config.yaml"
        log.debug("Loading config for %s", self.project.slug)
        try:
            with cfg_path.open() as f:
                cfg = yaml.safe_load(f) or {}
            self._localai_cfg = cfg.get("localai", {})
            self._output_type = self._localai_cfg.get("output_type", "text")
            self._run_command = self._localai_cfg.get("run_command", "")
            out_dir_rel       = self._localai_cfg.get("output_dir", "outputs/")
            self._output_dir  = _PROJECTS_DIR / self.project.slug / out_dir_rel
            log.debug("LocalAI config loaded: output_type=%s", self._output_type)
        except Exception:
            log.exception("Failed to load config for %s", self.project.slug)
            self._localai_cfg = {}

    # ── Compose ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        self._load_cfg()
        model   = self._localai_cfg.get("model",   "unknown model")
        purpose = self._localai_cfg.get("purpose",  "")
        meta    = f"{model}" + (f" · {purpose}" if purpose else "")

        yield Header()
        with Horizontal(id="top-bar"):
            yield Label(self.project.name, id="project-title")
            yield Label(meta,              id="project-meta")

        if not self._run_command:
            with Vertical(id="main-area"):
                yield Label(
                    "⚠  No run command configured. "
                    "This project may not have completed setup, or the config is missing.\n"
                    "Delete this project and create it again to re-run setup.",
                    id="no-setup-banner",
                )
        else:
            with Vertical(id="main-area"):
                yield Label("Prompt:", classes="section-label")
                yield TextArea("", id="prompt-input")

                if self._output_type == "file":
                    yield Label("Negative prompt (optional):", classes="section-label")
                    yield TextArea("", id="neg-input")

                with Horizontal(id="action-bar"):
                    yield Button("▶ Run",          id="btn-run",           variant="primary")
                    yield Button("Test Endpoint",   id="btn-test-ep")
                    yield Button("Browse Models",   id="btn-browse-models")
                    if self._output_type == "file":
                        yield Button("Open Output", id="btn-open", disabled=True)

                yield Label("Output:", id="output-label")
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
        if bid == "btn-run":
            prompt = self.query_one("#prompt-input", TextArea).text.strip()
            if not prompt:
                self.app.notify("Please enter a prompt.", severity="warning")
                return
            neg = ""
            if self._output_type == "file":
                try:
                    neg = self.query_one("#neg-input", TextArea).text.strip()
                except Exception:
                    pass
            log.info("Running inference: model=%s output_type=%s",
                     self._localai_cfg.get("model"), self._output_type)
            self.run_worker(self._run_inference(prompt, neg))

        elif bid == "btn-test-ep":
            self.run_worker(self._test_endpoint())

        elif bid == "btn-browse-models":
            from nexus.core.config_manager import load_global_config
            from modules.localai.model_browser_screen import ModelBrowserScreen
            endpoint = load_global_config().get("ai", {}).get(
                "local_endpoint", "http://localhost:11434"
            )
            self.app.push_screen(
                ModelBrowserScreen(self.project.slug, endpoint),
                self._on_model_selected,
            )

        elif bid == "btn-open":
            if self._last_output_file and self._last_output_file.exists():
                log.info("Opening output file: %s", self._last_output_file)
                try:
                    subprocess.Popen(open_path(self._last_output_file))
                except Exception:
                    log.exception("Failed to open output file")
                    self.app.notify("Could not open file.", severity="error")
            else:
                self.app.notify("No output file found yet.", severity="warning")

    # ── Endpoint test ─────────────────────────────────────────────────────────

    async def _test_endpoint(self) -> None:
        import time
        import httpx
        from nexus.core.config_manager import load_global_config
        ui_log = self.query_one("#output-log", Log)
        ai_cfg   = load_global_config().get("ai", {})
        endpoint = ai_cfg.get("local_endpoint", "http://localhost:11434").rstrip("/")
        ui_log.write_line(f"$ GET {endpoint}/v1/models")
        try:
            t0 = time.monotonic()
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(f"{endpoint}/v1/models")
            ms = int((time.monotonic() - t0) * 1000)
            if r.status_code == 200:
                models = r.json().get("data", [])
                first  = models[0]["id"] if models else "no models listed"
                ui_log.write_line(f"✓ Connected in {ms}ms  |  first model: {first}")
            else:
                ui_log.write_line(f"✗ HTTP {r.status_code} ({ms}ms)")
        except httpx.ConnectError:
            ui_log.write_line(f"✗ Could not connect to {endpoint}")
        except Exception as exc:
            log.exception("Test endpoint failed")
            ui_log.write_line(f"✗ {exc}")

    def _on_model_selected(self, model_id: str | None) -> None:
        if not model_id:
            return
        self._load_cfg()
        model   = self._localai_cfg.get("model", "")
        purpose = self._localai_cfg.get("purpose", "")
        meta    = model + (f" · {purpose}" if purpose else "")
        try:
            self.query_one("#project-meta", Label).update(meta)
        except Exception:
            pass

    # ── Inference worker ──────────────────────────────────────────────────────

    async def _run_inference(self, prompt: str, negative_prompt: str) -> None:
        import os
        ui_log = self.query_one("#output-log", Log)
        ui_log.clear()

        # Replace legacy {prompt}/{negative_prompt} placeholders with env var references.
        # Prompt values are passed via environment variables so they are never interpolated
        # into the shell command string — prevents shell injection from prompt content.
        cmd = self._run_command
        cmd = cmd.replace("{prompt}",          "$NEXUS_PROMPT")
        cmd = cmd.replace("{negative_prompt}", "$NEXUS_NEGATIVE_PROMPT")

        log.info("Inference command: %s", cmd[:120])
        ui_log.write_line(f"$ {cmd[:120]}{'…' if len(cmd) > 120 else ''}\n")

        if self._output_type == "file":
            try:
                self._output_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                log.exception("Could not create output dir")

        # Snapshot output dir before run (to detect new files)
        before: set[Path] = set()
        if self._output_type == "file" and self._output_dir.exists():
            before = {p for p in self._output_dir.iterdir() if p.is_file()}

        env = os.environ.copy()
        env["NEXUS_PROMPT"]          = prompt
        env["NEXUS_NEGATIVE_PROMPT"] = negative_prompt

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(_PROJECTS_DIR / self.project.slug),
                env=env,
            )
            if proc.stdout is None:
                ui_log.write_line("✗ Failed to open process stdout.")
                return
            async for raw_line in proc.stdout:
                ui_log.write_line(raw_line.decode(errors="replace").rstrip())
            await proc.wait()
            log.info("Inference process exited with code %d", proc.returncode)
        except Exception:
            log.exception("Inference execution failed")
            ui_log.write_line("\n✗ Unexpected error running inference — see log.")
            self.app.notify("Inference failed unexpectedly.", severity="error")
            return

        if proc.returncode != 0:
            ui_log.write_line(f"\n✗ Process exited with code {proc.returncode}.")
        else:
            ui_log.write_line("\n✓ Done.")

        # Find new output file
        if self._output_type == "file" and self._output_dir.exists():
            after = {p for p in self._output_dir.iterdir() if p.is_file()}
            new_files = sorted(after - before, key=lambda p: p.stat().st_mtime, reverse=True)
            if new_files:
                self._last_output_file = new_files[0]
                log.info("New output file: %s", self._last_output_file)
                ui_log.write_line(f"\n  Output saved: {self._last_output_file.name}")
                try:
                    self.query_one("#btn-open", Button).disabled = False
                except Exception:
                    pass
