from __future__ import annotations

import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Label, Button, Input, Log, TextArea
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.core.project_manager import ProjectInfo

log = get("sdforge.setup_screen")

_ALL_STEPS = ["step-config", "step-check", "step-review", "step-install", "step-done"]

_STEP_LABELS = {
    "step-config":  "Step 1 — Configure SD Forge",
    "step-check":   "Step 2 — Checking environment…",
    "step-review":  "Step 3 — Review install script",
    "step-install": "Step 4 — Installing…",
    "step-done":    "Setup complete",
}


def _build_launch_args(vram: str) -> str:
    args = ["--api"]
    m = re.search(r"(\d+(?:\.\d+)?)", vram.lower())
    gb = float(m.group(1)) if m else 0.0
    if gb >= 4:
        args.append("--xformers")
    elif gb > 0:
        args.append("--lowvram")
    else:
        args.extend(["--skip-torch-cuda-test", "--use-cpu=all"])
    return " ".join(args)


def _build_install_script(install_dir: str, launch_args: str) -> str:
    return f"""\
#!/bin/bash
set -e

INSTALL_DIR="{install_dir}"
REPO_URL="https://github.com/lllyasviel/stable-diffusion-webui-forge.git"

# ── Clone or update ───────────────────────────────────────────────────────────
if [ ! -d "$INSTALL_DIR" ]; then
    echo "Cloning SD Forge — this may take a while…"
    git clone "$REPO_URL" "$INSTALL_DIR"
else
    echo "Directory already exists — pulling latest changes…"
    git -C "$INSTALL_DIR" pull --ff-only || echo "(pull skipped — continuing with existing)"
fi

chmod +x "$INSTALL_DIR/webui.sh"

echo ""
echo "✓  SD Forge is ready at: $INSTALL_DIR"
echo "   First launch will download PyTorch + model weights (10–30 min)."
echo "   Start command: cd \\"$INSTALL_DIR\\" && ./webui.sh {launch_args}"
"""


class SDForgeSetupScreen(Screen):
    BINDINGS = [("escape", "dismiss", "Cancel")]

    DEFAULT_CSS = """
    SDForgeSetupScreen { background: #1A0A2E; align: center middle; }
    SDForgeSetupScreen Header { background: #2D1B4E; color: #00B4FF; }
    SDForgeSetupScreen Footer { background: #2D1B4E; color: #00FF88; }

    #dialog {
        background: #2D1B4E;
        border: solid #00B4FF;
        padding: 1 2;
        width: 90;
        height: auto;
        max-height: 50;
    }
    #dialog-title  { color: #00B4FF; text-style: bold; height: 2; }
    #step-label    { color: #666699; height: 1; margin-bottom: 1; }

    .field-label   { color: #00FF88; height: 1; margin-top: 1; }
    .hint          { color: #555588; height: 1; }
    Input          { margin-bottom: 0; }
    .error-label   { color: #FF4444; height: 1; }

    #check-log     { height: 10; background: #0A0518; border: solid #3A2260; }
    #review-area   { height: 18; background: #0A0518; border: solid #3A2260; }
    #install-log   { height: 18; background: #0A0518; border: solid #3A2260; }

    #btn-row       { height: 3; margin-top: 2; }
    #btn-row Button { margin-right: 1; }
    .ok-label      { color: #00FF88; }
    """

    def __init__(self, project: ProjectInfo):
        super().__init__()
        self.project         = project
        self._install_dir    = ""
        self._endpoint       = "http://localhost:7860"
        self._vram           = ""
        self._launch_args    = ""
        self._script         = ""
        self._already_installed = False

    # ── Compose ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="dialog"):
            yield Label("SD Forge Setup", id="dialog-title")
            yield Label(_STEP_LABELS["step-config"], id="step-label")

            # step-config ─────────────────────────────────────────────────────
            with Vertical(id="step-config"):
                yield Label("Install directory:", classes="field-label")
                yield Input(placeholder="~/stable-diffusion-webui-forge", id="input-install-dir")
                yield Label("API endpoint:", classes="field-label")
                yield Input(value="http://localhost:7860", id="input-endpoint")
                yield Label("Available VRAM (e.g. 8 GB, 4 GB, none):", classes="field-label")
                yield Input(placeholder="e.g. 8 GB", id="input-vram")
                yield Label("", id="config-error", classes="error-label")
                with Horizontal(id="btn-row"):
                    yield Button("Next →", id="btn-next", variant="primary")

            # step-check ──────────────────────────────────────────────────────
            with Vertical(id="step-check"):
                yield Label("Checking environment…", classes="field-label")
                yield Log(id="check-log", auto_scroll=True)

            # step-review ─────────────────────────────────────────────────────
            with Vertical(id="step-review"):
                yield Label("Review the install script (edit if needed):", classes="field-label")
                yield TextArea("", id="review-area")
                with Horizontal(id="btn-row"):
                    yield Button("← Back",      id="btn-back")
                    yield Button("Run Install", id="btn-run-install", variant="primary")

            # step-install ────────────────────────────────────────────────────
            with Vertical(id="step-install"):
                yield Label("Installing SD Forge…", classes="field-label")
                yield Log(id="install-log", auto_scroll=True)

            # step-done ───────────────────────────────────────────────────────
            with Vertical(id="step-done"):
                yield Label("", id="done-label", classes="ok-label")
                with Horizontal(id="btn-row"):
                    yield Button("Open Project", id="btn-finish", variant="primary")

        yield Footer()
        self._show("step-config")

    # ── Step navigation ───────────────────────────────────────────────────────

    def _show(self, step_id: str) -> None:
        for sid in _ALL_STEPS:
            self.query_one(f"#{sid}").display = (sid == step_id)
        self.query_one("#step-label", Label).update(_STEP_LABELS.get(step_id, ""))

    # ── Button handler ────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        try:
            self._handle_button(bid)
        except Exception:
            log.exception("Unhandled error in setup button handler (button=%s)", bid)

    def _handle_button(self, bid: str | None) -> None:
        if bid == "btn-next":
            self._do_next()
        elif bid == "btn-back":
            self._show("step-config")
        elif bid == "btn-run-install":
            script = self.query_one("#review-area", TextArea).text
            self._script = script
            self._show("step-install")
            self.run_worker(self._run_install(script))
        elif bid == "btn-finish":
            self.dismiss()

    def _do_next(self) -> None:
        install_dir = self.query_one("#input-install-dir", Input).value.strip()
        endpoint    = self.query_one("#input-endpoint",    Input).value.strip()
        vram        = self.query_one("#input-vram",        Input).value.strip()
        err_lbl     = self.query_one("#config-error",      Label)

        if not install_dir:
            err_lbl.update("Install directory is required.")
            return
        if not endpoint:
            endpoint = "http://localhost:7860"
        err_lbl.update("")

        self._install_dir = str(Path(install_dir).expanduser())
        self._endpoint    = endpoint
        self._vram        = vram or "none"
        self._launch_args = _build_launch_args(self._vram)

        self._show("step-check")
        self.run_worker(self._run_check())

    # ── Check worker ─────────────────────────────────────────────────────────

    async def _run_check(self) -> None:
        import asyncio
        import httpx
        from modules.localai.hw_detect import detect_hardware, format_hardware

        ck_log = self.query_one("#check-log", Log)
        ck_log.clear()
        ck_log.write_line("Detecting hardware…")
        try:
            hw = await asyncio.to_thread(detect_hardware)
            ck_log.write_line(format_hardware(hw))
        except Exception:
            ck_log.write_line("  (hardware detection failed — continuing)")

        ck_log.write_line("")
        git_ok = bool(shutil.which("git"))
        ck_log.write_line(f"git:     {'✓ found' if git_ok else '✗ NOT FOUND — install git before continuing'}")

        install_path = Path(self._install_dir)
        self._already_installed = (install_path / "webui.sh").exists()
        status = "already installed" if self._already_installed else "will be cloned"
        ck_log.write_line(f"forge:   {status} at {self._install_dir}")

        ck_log.write_line(f"launch:  {self._launch_args}")
        ck_log.write_line("")
        ck_log.write_line("Checking if endpoint is already reachable…")
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(self._endpoint.rstrip("/") + "/sdapi/v1/progress")
            if r.status_code == 200:
                ck_log.write_line(f"  ✓ SD Forge already running at {self._endpoint}")
            else:
                ck_log.write_line(f"  ✗ HTTP {r.status_code} (server may be offline — that is fine)")
        except Exception:
            ck_log.write_line(f"  (not reachable — will start later)")

        ck_log.write_line("")
        ck_log.write_line("Building install script…")
        self._script = _build_install_script(self._install_dir, self._launch_args)
        ck_log.write_line("✓ Done. Proceeding to review.")

        self.query_one("#review-area", TextArea).load_text(self._script)
        self._show("step-review")

    # ── Install worker ────────────────────────────────────────────────────────

    async def _run_install(self, script: str) -> None:
        import asyncio
        import os
        inst_log = self.query_one("#install-log", Log)
        inst_log.clear()

        # Write script to a temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False, prefix="nexus_sdforge_"
        ) as f:
            f.write(script)
            script_path = f.name

        try:
            os.chmod(script_path, 0o755)
            proc = await asyncio.create_subprocess_exec(
                "bash", script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            if proc.stdout is None:
                log.error("subprocess stdout is None — cannot stream output")
                return
            async for raw in proc.stdout:
                inst_log.write_line(raw.decode(errors="replace").rstrip())
            await proc.wait()
            log.info("SDForge install script exited with code %d", proc.returncode)
        except Exception:
            log.exception("SDForge install script execution failed")
            inst_log.write_line("\n✗ Unexpected error — see nexus log.")
            self.app.notify("Install failed — see log.", severity="error")
            return
        finally:
            try:
                Path(script_path).unlink(missing_ok=True)
            except Exception:
                pass

        if proc.returncode != 0:
            inst_log.write_line(f"\n✗ Script exited with code {proc.returncode}.")
            self.app.notify("Install script failed — see log.", severity="error")
            return

        inst_log.write_line("\n✓ Install script completed successfully.")
        self._save_config()
        self.query_one("#done-label", Label).update(
            f"✓  {self.project.name} is ready!\n\n"
            f"   Install dir: {self._install_dir}\n"
            f"   Endpoint:    {self._endpoint}\n"
            f"   Launch args: {self._launch_args}\n\n"
            f"   SD Forge will download PyTorch and models on first start."
        )
        self._show("step-done")

    # ── Config save ───────────────────────────────────────────────────────────

    def _save_config(self) -> None:
        from nexus.core.config_manager import load_project_config, save_project_config
        try:
            cfg = load_project_config(self.project.slug)
            cfg["sdforge"] = {
                "install_dir": self._install_dir,
                "endpoint":    self._endpoint,
                "vram":        self._vram,
                "model":       "",
                "launch_args": self._launch_args,
                "output_dir":  "outputs/",
                "setup_done":  True,
                "setup_at":    datetime.now(timezone.utc).isoformat(),
            }
            save_project_config(self.project.slug, cfg)
            log.info("SDForge config saved for project %s", self.project.slug)
        except Exception:
            log.exception("Failed to save SDForge config for %s", self.project.slug)
            self.app.notify("Failed to save config — see log.", severity="error")
