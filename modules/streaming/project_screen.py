from __future__ import annotations
from pathlib import Path

import platform as _platform
import shutil
from textual.widgets import Input, Label, Button, Log
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.core.platform import open_path, check_binary
from nexus.ui.base_project_screen import BaseProjectScreen, _screen_css

log = get("streaming.project_screen")


class StreamingProjectScreen(BaseProjectScreen):
    MODULE_KEY   = "streaming"
    MODULE_LABEL = "STREAMING"
    SETUP_FIELDS = [
        {"id": "obs_config_dir", "label": "OBS config directory",
         "placeholder": "~/.config/obs-studio", "type": "dir"},
        {"id": "platform", "label": "Streaming platform (twitch / youtube / local)",
         "placeholder": "twitch"},
        {"id": "obs_bin", "label": "OBS binary",
         "placeholder": "obs"},
    ]

    DEFAULT_CSS = _screen_css("StreamingProjectScreen")

    # ── Before-save hook ──────────────────────────────────────────────────────

    def _on_before_save(self, data: dict) -> dict:
        obs_bin = data.get("obs_bin", "obs")
        if not check_binary(obs_bin):
            raise ValueError(
                f"'{obs_bin}' not found on PATH. Install OBS or fix the binary path."
            )
        return {}

    # ── Setup auto-detection ──────────────────────────────────────────────────

    def on_mount(self) -> None:
        super().on_mount()
        if not self._is_configured():
            self.call_after_refresh(self._autofill_setup)

    def _autofill_setup(self) -> None:
        binary = shutil.which("obs") or shutil.which("obs-studio")
        try:
            inp = self.query_one("#setup-obs_bin", Input)
            if binary and not inp.value:
                inp.value = binary
        except Exception:
            pass
        if _platform.system() == "Darwin":
            default_cfg = Path.home() / "Library" / "Application Support" / "obs-studio"
        else:
            default_cfg = Path.home() / ".config" / "obs-studio"
        try:
            cfg_inp = self.query_one("#setup-obs_config_dir", Input)
            if default_cfg.exists() and not cfg_inp.value:
                cfg_inp.value = str(default_cfg)
        except Exception:
            pass

    # ── Action buttons ────────────────────────────────────────────────────────

    def _compose_action_buttons(self) -> list:
        return [
            Button("Launch OBS",   id="btn-launch-obs",  variant="primary"),
            Button("Check Logs",   id="btn-check-logs"),
            Button("List Scenes",  id="btn-list-scenes"),
            Button("Open Config",  id="btn-open-config"),
        ]

    # ── Main content ──────────────────────────────────────────────────────────

    async def _populate_content(self) -> None:
        area = self.query_one("#content-area", Vertical)
        await area.remove_children()

        obs_config_dir = Path(self._mod.get("obs_config_dir", "")).expanduser()
        platform       = self._mod.get("platform", "")
        obs_bin        = self._mod.get("obs_bin", "obs")
        config_exists  = obs_config_dir.exists()

        widgets: list = [
            Horizontal(
                Label("Platform:", classes="info-key"),
                Label(platform.upper() if platform else "—", classes="info-val"),
                classes="info-row",
            ),
            Horizontal(
                Label("OBS binary:", classes="info-key"),
                Label(obs_bin, classes="info-val"),
                classes="info-row",
            ),
            Horizontal(
                Label("Config dir:", classes="info-key"),
                Label(
                    str(obs_config_dir),
                    classes="info-val " + ("status-ok" if config_exists else "status-err"),
                ),
                classes="info-row",
            ),
        ]

        scenes_dir = obs_config_dir / "basic" / "scenes"
        if scenes_dir.exists():
            scene_files = sorted(scenes_dir.glob("*.json"))
            widgets.append(Label("Scene collections:", classes="section-label"))
            for sf in scene_files:
                widgets.append(Label(f"  {sf.stem}", classes="hint"))
            if not scene_files:
                widgets.append(Label("  No scene collections found.", classes="hint"))
        elif config_exists:
            widgets.append(Label("No scene collections found (basic/scenes/ missing).", classes="hint"))
        else:
            widgets.append(Label("OBS config directory not found — is OBS installed?", classes="hint"))

        await area.mount(*widgets)

    def _primary_folder(self) -> Path | None:
        p = Path(self._mod.get("obs_config_dir", "")).expanduser()
        return p if str(p) != "." else None

    # ── Button handler ────────────────────────────────────────────────────────

    def _handle_action(self, bid: str | None) -> None:
        obs_config_dir = Path(self._mod.get("obs_config_dir", "")).expanduser()
        obs_bin        = self._mod.get("obs_bin", "obs")

        if bid == "btn-launch-obs":
            import shutil
            if not shutil.which(obs_bin):
                self.app.notify(f"'{obs_bin}' not found on PATH.", severity="error")
                return
            self.run_worker(self._run_cmd([obs_bin]))

        elif bid == "btn-check-logs":
            logs_dir = obs_config_dir / "logs"
            if not logs_dir.exists():
                self.app.notify("OBS logs directory not found.", severity="warning")
                return
            log_files = sorted(logs_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not log_files:
                self.app.notify("No OBS log files found.", severity="warning")
                return
            latest_log = log_files[0]
            try:
                lines = latest_log.read_text(errors="replace").splitlines()[-50:]
                ui_log = self.query_one("#output-log")
                ui_log.clear()
                ui_log.write_line(f"--- {latest_log.name} (last 50 lines) ---")
                for line in lines:
                    ui_log.write_line(line)
                _WARN_KEYS = ("crash", "dropped frames", "output error", "recording error",
                              "encoding error", "connection failed")
                flagged = [l for l in lines if any(k in l.lower() for k in _WARN_KEYS)]
                if flagged:
                    ui_log.write_line(f"\n⚠ {len(flagged)} warning/issue line(s):")
                    for l in flagged[:5]:
                        ui_log.write_line(f"  {l.strip()}")
            except Exception:
                log.exception("Failed to read OBS log")
                self.app.notify("Could not read OBS log.", severity="error")

        elif bid == "btn-list-scenes":
            scenes_dir = obs_config_dir / "basic" / "scenes"
            self.run_worker(
                self._run_cmd(["find", str(scenes_dir), "-name", "*.json"])
                if scenes_dir.exists()
                else self._run_cmd(["echo", "No scenes directory found."])
            )

        elif bid == "btn-open-config":
            self.run_worker(self._run_cmd(open_path(obs_config_dir)))
