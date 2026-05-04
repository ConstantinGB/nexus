from __future__ import annotations
import asyncio
from datetime import datetime
from pathlib import Path

from textual.app import ComposeResult
from textual.css.query import NoMatches
from textual.widgets import Label, Button, Input, TextArea
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.core.config_manager import is_ai_configured
from nexus.ui.tui.base_project_screen import BaseProjectScreen, _screen_css

log = get("promptopt.project_screen")

_SYSTEM_PROMPTS = {
    "text": (
        "Rewrite the following prompt to be more precise, unambiguous, and AI-readable. "
        "Return only the improved prompt, no explanation."
    ),
    "instruct": (
        "Rewrite the following as a clear AI instruction. Use imperative tone, explicit "
        "constraints, and structured formatting. Return only the rewritten instruction."
    ),
    "image": (
        "Convert the following natural-language image description into a comma-separated "
        "tag-based prompt optimised for Stable Diffusion. Include style, lighting, "
        "composition, and quality tags. Return only the tag prompt."
    ),
}


class ProjectScreen(BaseProjectScreen):
    MODULE_KEY   = "promptopt"
    MODULE_LABEL = "PROMPT OPT"
    SETUP_FIELDS = [
        {"id": "save_dir", "label": "Save directory for prompts (optional)",
         "placeholder": "~/prompts", "type": "dir", "optional": True},
    ]

    DEFAULT_CSS = _screen_css("PromptOptProjectScreen") + """
    PromptOptProjectScreen #mode-row { height: 3; margin-bottom: 1; }
    PromptOptProjectScreen #mode-row Button { margin-right: 1; }
    PromptOptProjectScreen #input-prompt { margin-bottom: 1; }
    PromptOptProjectScreen #opt-btn-row { height: 3; margin-bottom: 1; }
    PromptOptProjectScreen #opt-btn-row Button { margin-right: 1; }
    PromptOptProjectScreen #output-area { height: 12; margin-bottom: 1; }
    """

    _mode: str = "text"

    def _is_configured(self) -> bool:
        return True

    def _compose_action_buttons(self) -> list:
        return []

    async def _populate_content(self) -> None:
        try:
            area = self.query_one("#content-area", Vertical)
        except Exception:
            return
        await area.remove_children()
        await area.mount(
            Horizontal(
                Button("Text",     id="btn-mode-text",    variant="primary"),
                Button("Instruct", id="btn-mode-instruct"),
                Button("Image",    id="btn-mode-image"),
                id="mode-row",
            ),
            Input(placeholder="Enter your prompt here…", id="input-prompt"),
            Horizontal(
                Button("Optimize", id="btn-optimize", variant="primary"),
                Button("Copy",     id="btn-copy",     disabled=True),
                Button("Save",     id="btn-save-out", disabled=True),
                id="opt-btn-row",
            ),
            TextArea(id="output-area"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid in ("btn-mode-text", "btn-mode-instruct", "btn-mode-image"):
            event.stop()
            self._mode = bid.removeprefix("btn-mode-")
            self._refresh_mode_buttons()
        else:
            super().on_button_pressed(event)

    def _refresh_mode_buttons(self) -> None:
        for mode in ("text", "instruct", "image"):
            try:
                btn = self.query_one(f"#btn-mode-{mode}", Button)
                btn.variant = "primary" if mode == self._mode else "default"
            except NoMatches:
                pass

    def _handle_action(self, bid: str | None) -> None:
        if bid == "btn-optimize":
            self.run_worker(self._do_optimize())
        elif bid == "btn-copy":
            try:
                text = self.query_one("#output-area", TextArea).text
                self.app.copy_to_clipboard(text)
                self.app.notify("Copied to clipboard.")
            except Exception:
                pass
        elif bid == "btn-save-out":
            self.run_worker(self._do_save_output())

    async def _do_optimize(self) -> None:
        try:
            input_widget  = self.query_one("#input-prompt", Input)
            output_widget = self.query_one("#output-area", TextArea)
            copy_btn      = self.query_one("#btn-copy", Button)
            save_btn      = self.query_one("#btn-save-out", Button)
        except Exception:
            return

        prompt = input_widget.value.strip()
        if not prompt:
            self.app.notify("Enter a prompt first.", severity="warning")
            return

        if not is_ai_configured():
            self.app.notify(
                "AI not configured — open Settings to add an API key or local model.",
                severity="warning",
            )
            return

        self.app.notify("Optimizing…", severity="information")
        try:
            from nexus.ai.client import AIClient
            client = AIClient()
            result = await client.chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=_SYSTEM_PROMPTS[self._mode],
            )
            try:
                output_widget.load_text(result)
                copy_btn.disabled = False
                save_btn.disabled = False
            except Exception:
                pass
        except Exception:
            log.exception("Optimize failed")
            self.app.notify("Optimization failed — see log.", severity="error")

    async def _do_save_output(self) -> None:
        try:
            text = self.query_one("#output-area", TextArea).text
        except Exception:
            return
        if not text.strip():
            self.app.notify("No output to save.", severity="warning")
            return

        save_dir_raw = self._mod.get("save_dir", "").strip()
        if save_dir_raw:
            save_dir = Path(save_dir_raw).expanduser()
        else:
            save_dir = Path(self.project.path)

        try:
            await asyncio.to_thread(save_dir.mkdir, parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = save_dir / f"{ts}.txt"
            await asyncio.to_thread(dest.write_text, text)
            self.app.notify(f"Saved: {dest.name}", severity="information")
        except Exception:
            log.exception("Failed to save prompt output")
            self.app.notify("Save failed — see log.", severity="error")
