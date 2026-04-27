from __future__ import annotations
import asyncio
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Label, Input, Button, Log, TextArea
from textual.containers import Vertical, Horizontal, ScrollableContainer

from nexus.core.logger import get
from nexus.core.project_manager import ProjectInfo

log = get("localai.setup_screen")

_PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"

_ALL_STEPS = ["step-config", "step-ai", "step-review", "step-install", "step-done"]

_STEP_LABELS = {
    "step-config":  "Step 1 — Configure your local AI",
    "step-ai":      "Step 2 — AI-assisted setup (detecting hardware + generating script…)",
    "step-review":  "Step 3 — Review the generated setup script",
    "step-install": "Step 4 — Running setup script…",
    "step-done":    "Setup complete",
}

# ---------------------------------------------------------------------------
# Claude prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert at setting up local AI models on Linux systems.

Your task: given the user's hardware and their requirements, produce a complete,
working bash setup script that downloads, installs, and configures the requested
AI model so it is ready to run.

You MUST respond with ONLY the structured format below — no prose, no explanation
outside the delimiters. The delimiters must appear exactly as shown.

---SETUP_SCRIPT---
#!/bin/bash
set -e
# ... complete bash script that installs everything needed ...
---END_SCRIPT---
---RUN_COMMAND---
# A shell command to run the model.
# The prompt is passed via the $NEXUS_PROMPT environment variable — use it directly.
# Use $NEXUS_NEGATIVE_PROMPT for negative prompts (diffusion models only).
# Example (LLM):   ollama run llama3.2 "$NEXUS_PROMPT"
# Example (image): python generate.py --prompt "$NEXUS_PROMPT" --negative "$NEXUS_NEGATIVE_PROMPT" --output outputs/image.png
---END_COMMAND---
---OUTPUT_TYPE---
text
---END_OUTPUT_TYPE---

OUTPUT_TYPE must be exactly "text" (for LLMs) or "file" (for diffusion/audio/video models).
The run command should be a single shell command that can be executed directly.
"""

_USER_PROMPT_TEMPLATE = """\
Please generate a setup script for the following local AI configuration:

## User Inputs
- Available VRAM: {vram}
- Purpose / Use case: {purpose}
- Requested model: {model}

## Detected Hardware
{hardware}

## Requirements
1. The setup script must install all required dependencies (Python packages, system packages,
   model weights, runtime environments, etc.).
2. Prefer lightweight, well-maintained tools: for LLMs prefer Ollama; for diffusion prefer
   ComfyUI or Stable Diffusion WebUI (automatic1111); match the tool to the model.
3. The script must be idempotent (safe to run twice).
4. Adapt the approach to the detected GPU — use CUDA for NVIDIA, ROCm for AMD, CPU-only if
   no GPU is detected.
5. Include model download steps in the script.
6. The run_command must work after setup completes.

Respond using ONLY the structured format from the system prompt.
"""


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def _parse_response(raw: str) -> tuple[str, str, str]:
    """Return (script, run_command, output_type). Falls back gracefully."""
    def _between(start: str, end: str) -> str:
        m = re.search(rf"{re.escape(start)}\s*(.*?)\s*{re.escape(end)}", raw, re.DOTALL)
        return m.group(1).strip() if m else ""

    script      = _between("---SETUP_SCRIPT---", "---END_SCRIPT---")
    run_command = _between("---RUN_COMMAND---",   "---END_COMMAND---")
    output_type = _between("---OUTPUT_TYPE---",   "---END_OUTPUT_TYPE---").lower()

    if not output_type:
        output_type = "file" if any(k in raw.lower() for k in
                                    ("image", "diffusion", "stable", "comfyui", "audio", "video")) else "text"
    if output_type not in ("text", "file"):
        output_type = "text"

    return script, run_command, output_type


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
        width: 86;
        height: auto;
        max-height: 46;
    }
    #dialog-title   { color: #00B4FF; text-style: bold; height: 2; }
    #step-label     { color: #666699; height: 1; margin-bottom: 1; }

    #ai-warning {
        background: #2A1500;
        border: solid #FFAA00;
        color: #FFAA00;
        padding: 0 1;
        height: 3;
        margin-bottom: 1;
    }
    #ai-warning-ok { color: #00FF88; height: 3; padding: 0 1; margin-bottom: 1; }

    .field-label  { color: #00FF88; height: 1; margin-top: 1; }
    .hint         { color: #555588; height: 2; }
    Input         { margin-bottom: 0; }

    #ai-log       { height: 14; background: #0A0518; border: solid #3A2260; }
    #review-area  { height: 18; background: #0A0518; border: solid #3A2260; }
    #install-log  { height: 16; background: #0A0518; border: solid #3A2260; }
    .parse-warn   { color: #FFAA00; height: 2; margin-bottom: 1; }

    #btn-row      { height: 3; margin-top: 2; }
    #btn-back     { margin-right: 1; }
    """

    def __init__(self, project: ProjectInfo):
        super().__init__()
        self.project      = project
        self._step        = "step-config"
        self._vram        = ""
        self._purpose     = ""
        self._model       = ""
        self._script      = ""
        self._run_command = ""
        self._output_type = "text"
        self._has_api_key = False

    # ── Compose ──────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        from nexus.core.config_manager import load_global_config
        cfg = load_global_config()
        api_key = cfg.get("ai", {}).get("api_key", "") or os.environ.get("ANTHROPIC_API_KEY", "")
        self._has_api_key = bool(api_key)

        yield Header()
        with Vertical(id="dialog"):
            yield Label("LocalAI Module Setup", id="dialog-title")
            yield Label(_STEP_LABELS["step-config"], id="step-label")

            # ── Step 1: Config ───────────────────────────────────────────
            with Vertical(id="step-config"):
                if self._has_api_key:
                    yield Label(
                        "⚠  AI Assisted Setup — Claude will analyse your hardware and "
                        "generate a tailored installation script.",
                        id="ai-warning-ok",
                    )
                else:
                    yield Label(
                        "⚠  AI Assisted Setup requires a Claude API key.\n"
                        "Configure one in the MCP screen (press m) before continuing.",
                        id="ai-warning",
                    )
                yield Label("Available VRAM (e.g. 8 GB, 16 GB, none):", classes="field-label")
                yield Input(placeholder="8 GB", id="input-vram")
                yield Label("Purpose (e.g. text generation, image generation, speech recognition):",
                            classes="field-label")
                yield Input(placeholder="text generation", id="input-purpose")
                yield Label("Model (e.g. llama3.2:7b, stable-diffusion-xl, whisper-large):",
                            classes="field-label")
                yield Input(placeholder="llama3.2:7b", id="input-model")
                yield Label(
                    "Claude will detect your hardware automatically and generate a setup script.",
                    classes="hint",
                )

            # ── Step 2: AI working ───────────────────────────────────────
            with Vertical(id="step-ai"):
                yield Label("Detecting hardware and consulting Claude…", classes="field-label")
                yield Log(id="ai-log", auto_scroll=True)

            # ── Step 3: Review ───────────────────────────────────────────
            with Vertical(id="step-review"):
                yield Label("Generated setup script (you may edit before running):",
                            classes="field-label")
                yield Label("", id="parse-warning", classes="parse-warn")
                yield TextArea("", id="review-area")

            # ── Step 4: Install ──────────────────────────────────────────
            with Vertical(id="step-install"):
                yield Label("Running setup script…", classes="field-label")
                yield Log(id="install-log", auto_scroll=True)

            # ── Step 5: Done ─────────────────────────────────────────────
            with Vertical(id="step-done"):
                yield Label("", id="done-label")

            with Horizontal(id="btn-row"):
                yield Button("← Back",   id="btn-back")
                yield Button("Initiate", id="btn-initiate", variant="primary")
                yield Button("Run Setup", id="btn-run-setup", variant="success")
                yield Button("Finish",    id="btn-finish",    variant="success")

        yield Footer()

    def on_mount(self) -> None:
        self._show("step-config")

    # ── Step display ─────────────────────────────────────────────────────────

    def _show(self, step: str) -> None:
        log.debug("Setup step: %s -> %s", self._step, step)
        self._step = step
        for sid in _ALL_STEPS:
            try:
                self.query_one(f"#{sid}").display = (sid == step)
            except Exception:
                pass
        self.query_one("#step-label", Label).update(_STEP_LABELS.get(step, ""))

        # Button visibility
        self.query_one("#btn-back",     Button).display = step in ("step-review",)
        self.query_one("#btn-initiate", Button).display = step == "step-config"
        self.query_one("#btn-run-setup",Button).display = step == "step-review"
        self.query_one("#btn-finish",   Button).display = step == "step-done"

    # ── Button handler ────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        try:
            self._handle_button(bid)
        except Exception:
            log.exception("Error in setup button handler (button=%s)", bid)
            self.app.notify("Unexpected error — see log.", severity="error")

    def _handle_button(self, bid: str | None) -> None:
        if bid == "btn-back":
            if self._step == "step-review":
                self._show("step-config")

        elif bid == "btn-initiate":
            if not self._has_api_key:
                self.app.notify(
                    "No Claude API key configured. Add one in the MCP screen (press m → API key).",
                    severity="error",
                )
                return
            vram    = self.query_one("#input-vram",    Input).value.strip()
            purpose = self.query_one("#input-purpose", Input).value.strip()
            model   = self.query_one("#input-model",   Input).value.strip()
            if not purpose or not model:
                self.app.notify("Please fill in Purpose and Model.", severity="error")
                return
            self._vram    = vram or "unknown"
            self._purpose = purpose
            self._model   = model
            log.info("Initiating AI setup: vram=%r purpose=%r model=%r",
                     self._vram, self._purpose, self._model)
            self._show("step-ai")
            self.run_worker(self._run_ai_setup())

        elif bid == "btn-run-setup":
            script = self.query_one("#review-area", TextArea).text.strip()
            if not script:
                self.app.notify("Setup script is empty.", severity="error")
                return
            self._script = script
            self._show("step-install")
            self.run_worker(self._run_install())

        elif bid == "btn-finish":
            self.dismiss()

    # ── AI setup worker ───────────────────────────────────────────────────────

    async def _run_ai_setup(self) -> None:
        from nexus.core.config_manager import load_global_config, merged_mcp_servers
        from nexus.ai.client import AIClient
        from nexus.ai.mcp_client import MCPClient
        from modules.localai.hw_detect import detect_hardware, format_hardware

        ui_log = self.query_one("#ai-log", Log)

        # 1. Detect hardware
        ui_log.write_line("Detecting hardware…")
        try:
            hw = await asyncio.get_event_loop().run_in_executor(None, detect_hardware)
            for line in format_hardware(hw).splitlines():
                ui_log.write_line(f"  {line}")
        except Exception:
            log.exception("Hardware detection failed")
            ui_log.write_line("  (hardware detection failed — Claude will proceed without it)")
            hw = {}

        # 2. Build prompt
        from modules.localai.hw_detect import format_hardware as _fmt
        hw_text = _fmt(hw) if hw else "Hardware detection unavailable."
        user_msg = _USER_PROMPT_TEMPLATE.format(
            vram=self._vram, purpose=self._purpose,
            model=self._model, hardware=hw_text,
        )

        # 3. Connect MCP (optional — for web fetch tools)
        cfg     = load_global_config()
        api_key = cfg.get("ai", {}).get("api_key", "") or os.environ.get("ANTHROPIC_API_KEY", "")
        servers = merged_mcp_servers()
        mcp: MCPClient | None = None
        if servers:
            ui_log.write_line(f"\nConnecting to {len(servers)} MCP server(s)…")
            mcp = MCPClient()
            try:
                await mcp.connect_all(servers)
                tools = await mcp.get_tools()
                ui_log.write_line(f"  {len(tools)} tools available.")
            except Exception:
                log.exception("MCP connect failed — proceeding without web tools")
                ui_log.write_line("  (MCP connect failed — proceeding without web tools)")
                mcp = None

        # 4. Call Claude
        ui_log.write_line("\nAsking Claude to generate the setup script…")
        ui_log.write_line("(This may take a minute — Claude may search the web for installation details.)")
        raw = ""
        try:
            ai = AIClient(api_key=api_key, mcp=mcp)
            raw = await ai.chat(
                [{"role": "user", "content": user_msg}],
                system_prompt=_SYSTEM_PROMPT,
            )
            log.info("Claude response received (%d chars)", len(raw))
        except Exception:
            log.exception("Claude API call failed")
            ui_log.write_line("\n✗ Claude API call failed — see log for details.")
            self.app.notify("Claude API call failed.", severity="error")
            self._show("step-config")
            return
        finally:
            if mcp:
                try:
                    await mcp.disconnect_all()
                except Exception:
                    log.warning("MCP disconnect error", exc_info=True)

        # 5. Parse response
        script, run_command, output_type = _parse_response(raw)
        self._run_command = run_command
        self._output_type = output_type

        parse_ok = bool(script and run_command)
        if not parse_ok:
            log.warning("Could not parse Claude response — showing raw output")
            script = raw  # show raw so user can still copy-paste

        self._show("step-review")
        self.query_one("#review-area", TextArea).load_text(script)
        if not parse_ok:
            self.query_one("#parse-warning", Label).update(
                "⚠  Could not parse structured response — raw Claude output shown. "
                "Copy the script manually if needed."
            )
        else:
            self.query_one("#parse-warning", Label).update("")

    # ── Install worker ────────────────────────────────────────────────────────

    async def _run_install(self) -> None:
        ui_log  = self.query_one("#install-log", Log)
        project_dir = _PROJECTS_DIR / self.project.slug

        # Write script to disk
        script_path = project_dir / "setup.sh"
        try:
            script_path.write_text(self._script)
            script_path.chmod(0o755)
            log.info("Setup script written: %s", script_path)
        except Exception:
            log.exception("Failed to write setup.sh")
            ui_log.write_line("✗ Could not write setup.sh — see log.")
            self.app.notify("Failed to write setup script.", severity="error")
            return

        ui_log.write_line(f"Running {script_path}…\n")

        # Stream subprocess output
        try:
            proc = await asyncio.create_subprocess_exec(
                "bash", str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(project_dir),
            )
            if proc.stdout is None:
                log.error("subprocess stdout is None — cannot stream output")
                return
            async for raw_line in proc.stdout:
                ui_log.write_line(raw_line.decode(errors="replace").rstrip())
            await proc.wait()
            ok = proc.returncode == 0
            log.info("Setup script exited with code %d", proc.returncode)
        except Exception:
            log.exception("Setup script execution failed")
            ui_log.write_line("\n✗ Unexpected error running setup.sh — see log.")
            self.app.notify("Setup script failed unexpectedly.", severity="error")
            return

        if ok:
            ui_log.write_line("\n✓ Setup script completed successfully.")
            self._save_config()
            self._show("step-done")
            self.query_one("#done-label", Label).update(
                f"✓  {self.project.name} is ready!\n"
                f"   Model: {self._model}   Output: {self._output_type}"
            )
        else:
            ui_log.write_line(f"\n✗ Setup script exited with code {proc.returncode}.")
            self.app.notify(
                "Setup script failed. Review the log and try editing the script.",
                severity="error",
            )

    # ── Config save ───────────────────────────────────────────────────────────

    def _save_config(self) -> None:
        cfg_path = _PROJECTS_DIR / self.project.slug / "config.yaml"
        log.info("Saving LocalAI config for %s", self.project.slug)
        try:
            with cfg_path.open() as f:
                cfg = yaml.safe_load(f) or {}
            cfg["localai"] = {
                "vram":        self._vram,
                "purpose":     self._purpose,
                "model":       self._model,
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
            log.exception("Failed to save LocalAI config for %s", self.project.slug)
            self.app.notify("Failed to save config — see log.", severity="error")
