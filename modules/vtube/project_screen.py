from __future__ import annotations
import shutil
from pathlib import Path

from textual.widgets import Label, Button, Log
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.core.platform import open_path, check_binary
from nexus.ui.base_project_screen import BaseProjectScreen, _screen_css

log = get("vtube.project_screen")

_TRACKER_INSTRUCTIONS = {
    "arkit": (
        "ARKit tracking runs on your iPhone/iPad.\n"
        "Use VTubeStudio's iOS app or iFacialMocap to stream to PC."
    ),
    "ifacialmocap": (
        "iFacialMocap: open the iOS app and connect to your PC IP.\n"
        "Set the receiver port in VSeeFace or VTubeStudio settings."
    ),
}

_MODEL_FORMAT = {
    ".moc3": "Live2D (.moc3 + .model3.json)",
    ".vrm":  "VRM 3D model",
    ".vsf":  "VSeeFace native (.vsf)",
}


class VTubeProjectScreen(BaseProjectScreen):
    MODULE_KEY   = "vtube"
    MODULE_LABEL = "VTUBE"
    SETUP_FIELDS = [
        {"id": "model_path",        "label": "Avatar model file (.moc3 or .vrm)",
         "placeholder": "~/avatars/my-model/model.moc3"},
        {"id": "runtime",           "label": "Runtime (vtubestudio / vseefface / vnyan / 3tene)",
         "placeholder": "vtubestudio"},
        {"id": "tracker",           "label": "Face tracker (arkit / openSeeFace / ifacialmocap)",
         "placeholder": "openSeeFace"},
        {"id": "openseeface_port",  "label": "OpenSeeFace receiver port (optional)",
         "placeholder": "11573", "optional": True},
    ]

    DEFAULT_CSS = _screen_css("VTubeProjectScreen")

    # ── Before-save hook ──────────────────────────────────────────────────────

    def _on_before_save(self, data: dict) -> dict:
        model_path = Path(data.get("model_path", "")).expanduser()
        runtime    = data.get("runtime", "")
        if not model_path.exists():
            self.app.notify(
                f"Model file not found: {model_path.name} — saved anyway.",
                severity="warning",
            )
        if runtime and not check_binary(runtime):
            self.app.notify(
                f"Runtime '{runtime}' not found on PATH — saved anyway.",
                severity="warning",
            )
        return {}

    # ── Action buttons ────────────────────────────────────────────────────────

    def _compose_action_buttons(self) -> list:
        return [
            Button("Launch Runtime",  id="btn-launch-runtime", variant="primary"),
            Button("Start Tracker",   id="btn-start-tracker"),
            Button("Check Camera",    id="btn-check-camera"),
            Button("Open Model Dir",  id="btn-open-model-dir"),
        ]

    # ── Main content ──────────────────────────────────────────────────────────

    async def _populate_content(self) -> None:
        area = self.query_one("#content-area", Vertical)
        await area.remove_children()

        model_path = Path(self._mod.get("model_path", "")).expanduser()
        runtime    = self._mod.get("runtime", "")
        tracker    = self._mod.get("tracker", "")
        ext        = model_path.suffix.lower()
        fmt        = _MODEL_FORMAT.get(ext, f"Unknown ({ext})" if ext else "—")

        pipeline = f"Camera  →  {tracker or '?'}  →  {runtime or '?'}  →  OBS"

        widgets: list = [
            Label("Tracking pipeline:", classes="section-label"),
            Label(f"  {pipeline}", classes="info-val"),
            Label("", classes="hint"),
            Horizontal(
                Label("Model:", classes="info-key"),
                Label(str(model_path), classes="info-val"),
                classes="info-row",
            ),
            Horizontal(
                Label("Format:", classes="info-key"),
                Label(fmt, classes="info-val"),
                classes="info-row",
            ),
            Horizontal(
                Label("Runtime:", classes="info-key"),
                Label(runtime or "—", classes="info-val"),
                classes="info-row",
            ),
            Horizontal(
                Label("Tracker:", classes="info-key"),
                Label(tracker or "—", classes="info-val"),
                classes="info-row",
            ),
        ]
        osf_port = self._mod.get("openseeface_port", "").strip()
        if osf_port or tracker.lower() == "openseeface":
            widgets.append(
                Horizontal(
                    Label("OSF port:", classes="info-key"),
                    Label(osf_port or "11573 (default)", classes="info-val"),
                    classes="info-row",
                )
            )

        model_exists = model_path.exists()
        widgets.append(
            Horizontal(
                Label("Model file:", classes="info-key"),
                Label(
                    "found" if model_exists else "not found",
                    classes="info-val " + ("status-ok" if model_exists else "status-err"),
                ),
                classes="info-row",
            )
        )

        await area.mount(*widgets)

    def _primary_folder(self) -> Path | None:
        mp = Path(self._mod.get("model_path", "")).expanduser()
        p = mp.parent if mp.suffix else mp
        return p if str(p) not in (".", "") else None

    # ── Button handler ────────────────────────────────────────────────────────

    def _handle_action(self, bid: str | None) -> None:
        model_path = Path(self._mod.get("model_path", "")).expanduser()
        runtime    = self._mod.get("runtime", "")
        tracker    = self._mod.get("tracker", "").lower()

        if bid == "btn-launch-runtime":
            if not runtime:
                self.app.notify("No runtime configured.", severity="warning")
                return
            if shutil.which(runtime):
                self.run_worker(self._run_cmd([runtime]))
            else:
                self.app.notify(
                    f"'{runtime}' not found on PATH — launch it manually.",
                    severity="warning",
                )

        elif bid == "btn-start-tracker":
            if tracker == "openseeface":
                # OpenSeeFace facetracker.py path often user-specific; show command
                ui_log = self.query_one("#output-log")
                ui_log.write_line(
                    "To start OpenSeeFace, run in your terminal:\n"
                    "  python facetracker.py -c 0 -v 3 --model 3\n"
                    "(from the OpenSeeFace directory)"
                )
                self.app.notify("OpenSeeFace command logged.", severity="information")
            elif tracker in _TRACKER_INSTRUCTIONS:
                ui_log = self.query_one("#output-log")
                ui_log.write_line(_TRACKER_INSTRUCTIONS[tracker])
            else:
                ui_log = self.query_one("#output-log")
                ui_log.write_line(f"Tracker '{tracker}': launch it according to its documentation.")

        elif bid == "btn-check-camera":
            self.run_worker(self._run_cmd(["v4l2-ctl", "--list-devices"]))

        elif bid == "btn-open-model-dir":
            model_dir = model_path.parent if model_path.suffix else model_path
            self.run_worker(self._run_cmd(open_path(model_dir)))
