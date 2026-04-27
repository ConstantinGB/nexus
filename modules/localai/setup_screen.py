from __future__ import annotations
import asyncio
import shutil
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Header, Footer, Label, Input, Button, Log, Switch, TabbedContent, TabPane,
)
from textual.containers import Vertical, Horizontal, ScrollableContainer

from nexus.core.logger import get
from nexus.core.project_manager import ProjectInfo
from modules.localai import model_catalog
from modules.localai.hw_detect import (
    detect_hardware, save_hardware_json, load_hardware_json,
)

log = get("localai.setup_screen")

_PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"

_ALL_STEPS = ["step-hw", "step-model", "step-pulling", "step-done"]

_STEP_LABELS = {
    "step-hw":      "Step 1 of 3 — Hardware detection",
    "step-model":   "Step 2 of 3 — Pick a model",
    "step-pulling": "Pulling model…",
    "step-done":    "Setup complete",
}

_FIT_LABELS: dict[str, tuple[str, str]] = {
    "recommended": ("★ GPU fit",   "#00FF88"),
    "fits":        ("~ GPU tight", "#FFFF44"),
    "cpu-only":    ("CPU only",    "#00B4FF"),
    "too-large":   ("✗ Too large", "#FF4444"),
}

_FIT_ORDER: dict[str, int] = {"recommended": 0, "cpu-only": 1, "fits": 2, "too-large": 3}


import re as _re

def _san(s: str) -> str:
    return _re.sub(r'[^a-zA-Z0-9_-]', '-', s)


# ---------------------------------------------------------------------------
# Embedded model row for the setup picker
# ---------------------------------------------------------------------------

class SetupModelRow(Horizontal):
    """Compact model row used in the setup screen's model picker."""

    DEFAULT_CSS = """
    SetupModelRow {
        height: 2; padding: 0 1;
        border-bottom: solid #241540;
    }
    SetupModelRow:hover { background: #2D1B4E; }
    SetupModelRow.row-selected { background: #0E2A0E; }
    SetupModelRow .mr-id   { width: 20; color: #E0E0FF; content-align: left middle; }
    SetupModelRow .mr-size { width: 6;  color: #8080AA; content-align: left middle; }
    SetupModelRow .mr-fit  { width: 12; content-align: left middle; }
    SetupModelRow .mr-fit-recommended { color: #00FF88; }
    SetupModelRow .mr-fit-fits        { color: #FFFF44; }
    SetupModelRow .mr-fit-cpu-only    { color: #00B4FF; }
    SetupModelRow .mr-fit-too-large   { color: #FF4444; }
    SetupModelRow .mr-fit-none        { color: #555555; }
    SetupModelRow .mr-desc { width: 1fr; color: #555588; content-align: left middle; }
    SetupModelRow Button   { width: 9; height: 2; min-width: 7; margin-left: 1; }
    """

    def __init__(self, model: dict, hw: dict, **kwargs) -> None:
        super().__init__(**kwargs)
        self._model = model
        self._hw    = hw

    def compose(self) -> ComposeResult:
        m   = self._model
        fit = model_catalog.fit_rating(m, self._hw) if self._hw else None
        fit_text = _FIT_LABELS[fit][0] if fit in _FIT_LABELS else ""
        fit_cls  = f"mr-fit mr-fit-{fit or 'none'}"

        yield Label(m["id"],              classes="mr-id")
        yield Label(m.get("size", ""),    classes="mr-size")
        yield Label(fit_text,             classes=fit_cls)
        yield Label(m.get("desc", ""),    classes="mr-desc")
        yield Button("Select", id=f"sel-{_san(m['id'])}", variant="primary")


# ---------------------------------------------------------------------------
# Setup screen
# ---------------------------------------------------------------------------

class LocalAISetupScreen(Screen):
    BINDINGS = [("escape", "dismiss", "Cancel")]

    DEFAULT_CSS = """
    LocalAISetupScreen { background: #1A0A2E; align: center middle; }
    LocalAISetupScreen Header { background: #2D1B4E; color: #00B4FF; }
    LocalAISetupScreen Footer { background: #2D1B4E; color: #00FF88; }

    #dialog {
        background: #2D1B4E;
        border: solid #00B4FF;
        padding: 1 2;
        width: 90;
        height: auto;
        max-height: 54;
    }
    #dialog-title { color: #00B4FF; text-style: bold; height: 2; }
    #step-label   { color: #666699; height: 1; margin-bottom: 1; }

    /* Step 1 — Hardware */
    #hw-status    { color: #8080AA; height: 1; margin-bottom: 1; }
    .hw-row       { height: 1; }
    .hw-key       { color: #8080AA; width: 8; }
    .hw-val       { color: #E0E0FF; width: 1fr; }
    #ollama-warn  { color: #FFAA00; height: 2; margin-top: 1; }

    /* Step 2 — Model picker */
    #search-bar         { height: 3; margin-bottom: 1; }
    #search-bar Label   { width: 10; color: #00FF88; content-align: left middle; }
    #search-bar Input   { width: 1fr; }
    #model-tabs         { height: 20; }
    .tab-empty          { color: #555588; padding: 1 1; height: 2; }
    #selected-label     { color: #00FF88; height: 1; margin-top: 1; }
    #pull-row           { height: 3; margin-top: 1; }
    #pull-row Switch    { width: 10; }
    #pull-row Label     { color: #E0E0FF; content-align: left middle; }
    #btn-advanced       { width: 18; margin-top: 1; }
    #advanced-pane      { margin-top: 1; }
    .field-label        { color: #00FF88; height: 1; margin-top: 1; }
    #custom-cmd         { margin-top: 1; }

    /* Step 3 — Pulling */
    #pull-log     { height: 16; background: #0A0518; border: solid #3A2260; }

    /* Step 4 — Done */
    #done-label   { color: #00FF88; height: 1; }
    #done-details { color: #E0E0FF; height: auto; margin-top: 1; }

    /* Buttons */
    #btn-row      { height: 3; margin-top: 2; }
    #btn-back     { margin-right: 1; }
    """

    def __init__(self, project: ProjectInfo) -> None:
        super().__init__()
        self.project               = project
        self._step                 = "step-hw"
        self._hw: dict             = {}
        self._selected_model       = ""
        self._selected_model_data: dict = {}
        self._run_command          = ""
        self._output_type          = "text"
        self._advanced_visible     = False
        self._installed: set[str]  = set()

    # ── Compose ──────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="dialog"):
            yield Label("LocalAI Setup", id="dialog-title")
            yield Label(_STEP_LABELS["step-hw"], id="step-label")

            # Step 1 — Hardware
            with Vertical(id="step-hw"):
                yield Label("Detecting hardware…", id="hw-status")
                with Vertical(id="hw-table"):
                    pass
                yield Label("", id="ollama-warn")

            # Step 2 — Model picker
            with Vertical(id="step-model"):
                with Horizontal(id="search-bar"):
                    yield Label("Search:")
                    yield Input(placeholder="name, tag, or description…", id="model-search")
                with TabbedContent(id="model-tabs"):
                    with TabPane("Catalog", id="tab-catalog"):
                        yield ScrollableContainer(id="catalog-list")
                    with TabPane("Installed", id="tab-installed"):
                        yield ScrollableContainer(id="installed-list")
                yield Label("No model selected — click Select on a row.", id="selected-label")
                with Horizontal(id="pull-row"):
                    yield Switch(value=True, id="pull-switch")
                    yield Label("Pull model now via Ollama")
                yield Button("Advanced ▼", id="btn-advanced")
                with Vertical(id="advanced-pane"):
                    yield Label("Custom run command (overrides auto-generated):",
                                classes="field-label")
                    yield Input(
                        placeholder='ollama run mymodel "$NEXUS_PROMPT"',
                        id="custom-cmd",
                    )

            # Step 3 — Pulling
            with Vertical(id="step-pulling"):
                yield Label("Pulling model — please wait…", classes="field-label")
                yield Log(id="pull-log", auto_scroll=True)

            # Step 4 — Done
            with Vertical(id="step-done"):
                yield Label("✓  Setup complete!", id="done-label")
                yield Label("", id="done-details")

            with Horizontal(id="btn-row"):
                yield Button("← Back",  id="btn-back")
                yield Button("Next →",  id="btn-next",   variant="primary")
                yield Button("Finish",  id="btn-finish", variant="success")

        yield Footer()

    def on_mount(self) -> None:
        try:
            self.query_one("#advanced-pane").display = False
        except Exception:
            pass
        self._show("step-hw")
        self.run_worker(self._detect_hardware())

    # ── Step management ──────────────────────────────────────────────────────

    def _show(self, step: str) -> None:
        log.debug("Setup step: %s → %s", self._step, step)
        self._step = step
        for sid in _ALL_STEPS:
            try:
                self.query_one(f"#{sid}").display = (sid == step)
            except Exception:
                pass
        try:
            self.query_one("#step-label", Label).update(_STEP_LABELS.get(step, ""))
        except Exception:
            pass
        try:
            self.query_one("#btn-back",   Button).display = step == "step-model"
            self.query_one("#btn-next",   Button).display = step in ("step-hw", "step-model")
            self.query_one("#btn-finish", Button).display = step == "step-done"
        except Exception:
            pass

    # ── Hardware detection ───────────────────────────────────────────────────

    async def _detect_hardware(self) -> None:
        try:
            hw_status = self.query_one("#hw-status", Label)
        except Exception:
            return
        try:
            hw = await asyncio.get_event_loop().run_in_executor(None, detect_hardware)
            self._hw = hw
            save_hardware_json(self.project.slug, hw)
        except Exception:
            log.exception("Hardware detection failed")
            hw = {}
            self._hw = {}

        try:
            hw_table = self.query_one("#hw-table", Vertical)
            await hw_table.remove_children()
            if hw:
                for key, val in [
                    ("OS",   hw.get("os",   "—")),
                    ("CPU",  hw.get("cpu",  "—")),
                    ("RAM",  hw.get("ram",  "—")),
                    ("GPU",  hw.get("gpu",  "—")),
                    ("Disk", hw.get("disk", "—")),
                ]:
                    await hw_table.mount(
                        Horizontal(
                            Label(f"{key}:", classes="hw-key"),
                            Label(val,        classes="hw-val"),
                            classes="hw-row",
                        )
                    )
                hw_status.update("✓ Hardware detected")
            else:
                hw_status.update("⚠  Hardware detection failed — you can still continue")
        except Exception:
            log.exception("Failed to build hw table")

        try:
            warn = self.query_one("#ollama-warn", Label)
            if not shutil.which("ollama"):
                warn.update(
                    "⚠  'ollama' not on PATH — you can still pick a model "
                    "and pull later from the project screen."
                )
        except Exception:
            pass

    # ── Model picker ─────────────────────────────────────────────────────────

    async def _enter_model_step(self) -> None:
        snapshot = frozenset(self._installed)
        query    = ""
        try:
            query = self.query_one("#model-search", Input).value.strip()
        except Exception:
            pass
        await self._rebuild_catalog(model_catalog.search(query), snapshot)
        self.run_worker(self._fetch_installed())

    async def _rebuild_catalog(self, models: list[dict], installed: frozenset) -> None:
        try:
            container = self.query_one("#catalog-list", ScrollableContainer)
        except Exception:
            return
        await container.remove_children()
        if not models:
            await container.mount(Label("No models match.", classes="tab-empty"))
            return
        hw = self._hw
        models_sorted = sorted(
            models,
            key=lambda m: _FIT_ORDER.get(model_catalog.fit_rating(m, hw), 4),
        )
        for m in models_sorted:
            await container.mount(
                SetupModelRow(m, self._hw,
                              classes="row-selected" if m["id"] == self._selected_model else "")
            )

    async def _rebuild_installed(self) -> None:
        try:
            container = self.query_one("#installed-list", ScrollableContainer)
        except Exception:
            return
        await container.remove_children()
        if not self._installed:
            await container.mount(
                Label("No models found — is Ollama running?", classes="tab-empty")
            )
            return
        for mid in sorted(self._installed):
            entry = model_catalog.get_by_id(mid) or {
                "id": mid, "display": mid, "size": "",
                "tags": [], "desc": "(not in catalog)", "vram_min_gb": 0.0,
            }
            await container.mount(
                SetupModelRow(entry, self._hw,
                              classes="row-selected" if mid == self._selected_model else "")
            )

    async def _fetch_installed(self) -> None:
        from nexus.core.config_manager import load_global_config
        endpoint = load_global_config().get("ai", {}).get(
            "local_endpoint", "http://localhost:11434"
        ).rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{endpoint}/v1/models")
            if resp.status_code == 200:
                self._installed = {item["id"] for item in resp.json().get("data", [])}
            else:
                self._installed = set()
        except Exception:
            self._installed = set()
        await self._rebuild_installed()

    # ── Model selection ───────────────────────────────────────────────────────

    def _select_model(self, model: dict) -> None:
        self._selected_model      = model["id"]
        self._selected_model_data = model
        try:
            self.query_one("#selected-label", Label).update(
                f"Selected: {model['id']}  ({model.get('size', '?')})"
            )
        except Exception:
            pass

    # ── Event handlers ────────────────────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "model-search" and self._step == "step-model":
            snapshot = frozenset(self._installed)
            self.run_worker(
                self._rebuild_catalog(model_catalog.search(event.value.strip()), snapshot)
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        # Model selection rows
        if bid.startswith("sel-"):
            row = event.button.parent
            if isinstance(row, SetupModelRow):
                self._select_model(row._model)
            return
        try:
            self._handle_button(bid)
        except Exception:
            log.exception("Setup button error: %s", bid)
            self.app.notify("Unexpected error — see log.", severity="error")

    def _handle_button(self, bid: str) -> None:
        if bid == "btn-back":
            if self._step == "step-model":
                self._show("step-hw")

        elif bid == "btn-next":
            if self._step == "step-hw":
                self._show("step-model")
                self.run_worker(self._enter_model_step())

            elif self._step == "step-model":
                if not self._selected_model:
                    self.app.notify("Please select a model first.", severity="warning")
                    return
                # Build run command
                custom = ""
                try:
                    custom = self.query_one("#custom-cmd", Input).value.strip()
                except Exception:
                    pass
                self._run_command = (
                    custom or f'ollama run {self._selected_model} "$NEXUS_PROMPT"'
                )
                self._output_type = "text"

                pull_now = True
                try:
                    pull_now = self.query_one("#pull-switch", Switch).value
                except Exception:
                    pass

                if pull_now:
                    if not shutil.which("ollama"):
                        self.app.notify(
                            "Ollama not on PATH — skipping pull. "
                            "Pull later from the project screen.",
                            severity="warning",
                        )
                        self._save_config()
                        self._show("step-done")
                        self._update_done_label()
                    else:
                        self._show("step-pulling")
                        self.run_worker(self._pull_model())
                else:
                    self._save_config()
                    self._show("step-done")
                    self._update_done_label()

        elif bid == "btn-advanced":
            self._advanced_visible = not self._advanced_visible
            try:
                self.query_one("#advanced-pane").display = self._advanced_visible
                self.query_one("#btn-advanced", Button).label = (
                    "Advanced ▲" if self._advanced_visible else "Advanced ▼"
                )
            except Exception:
                pass

        elif bid == "btn-finish":
            self.dismiss()

    # ── Pull worker ───────────────────────────────────────────────────────────

    async def _pull_model(self) -> None:
        try:
            pull_log = self.query_one("#pull-log", Log)
        except Exception:
            return
        try:
            pull_log.write_line(f"$ ollama pull {self._selected_model}")
        except Exception:
            return

        proc = None
        ok   = False
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "pull", self._selected_model,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            if proc.stdout is None:
                try:
                    pull_log.write_line("✗ ollama pull: stdout unavailable")
                except Exception:
                    pass
                return
            async for raw in proc.stdout:
                try:
                    pull_log.write_line(raw.decode(errors="replace").rstrip())
                except Exception:
                    break
            await proc.wait()
            ok = proc.returncode == 0
        except FileNotFoundError:
            try:
                pull_log.write_line("✗ 'ollama' not found on PATH.")
            except Exception:
                pass
        except Exception:
            log.exception("Pull failed: %s", self._selected_model)
            try:
                pull_log.write_line("✗ Unexpected error — see log.")
            except Exception:
                pass
        finally:
            if proc is not None and proc.returncode is None:
                try:
                    await proc.wait()
                except Exception:
                    pass

        self._save_config()
        try:
            if ok:
                pull_log.write_line(f"\n✓ {self._selected_model} pulled.")
            else:
                pull_log.write_line(
                    "\n⚠  Pull failed or skipped. Pull later from the project screen."
                )
        except Exception:
            pass
        self._show("step-done")
        self._update_done_label()

    # ── Config save ───────────────────────────────────────────────────────────

    def _save_config(self) -> None:
        cfg_path = _PROJECTS_DIR / self.project.slug / "config.yaml"
        log.info("Saving LocalAI config for %s", self.project.slug)
        try:
            try:
                with cfg_path.open() as f:
                    cfg = yaml.safe_load(f) or {}
            except FileNotFoundError:
                cfg = {}
            cfg["localai"] = {
                "model":       self._selected_model,
                "purpose":     "",
                "output_type": self._output_type,
                "run_command": self._run_command,
                "output_dir":  "outputs/",
                "setup_done":  True,
                "setup_at":    datetime.now(timezone.utc).isoformat(),
            }
            with cfg_path.open("w") as f:
                yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
            log.debug("LocalAI config saved")
        except Exception:
            log.exception("Failed to save LocalAI config")
            self.app.notify("Failed to save config — see log.", severity="error")

    def _update_done_label(self) -> None:
        try:
            self.query_one("#done-details", Label).update(
                f"Model:   {self._selected_model}\n"
                f"Command: {self._run_command}\n\n"
                "Use the Docker button on the project screen to start Ollama if needed."
            )
        except Exception:
            pass
