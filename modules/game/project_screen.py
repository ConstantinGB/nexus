from __future__ import annotations
import asyncio
import configparser
import shutil
from pathlib import Path

from textual.widgets import Input, Label, Button, Log
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.core.platform import check_binary
from nexus.ui.base_project_screen import BaseProjectScreen, _screen_css

log = get("game.project_screen")


def _read_godot_project(project_path: Path) -> dict:
    """Read project.godot and return game name and config version."""
    godot_file = project_path / "project.godot"
    result = {"game_name": project_path.name, "godot_version": "4"}
    if not godot_file.exists():
        return result
    try:
        parser = configparser.RawConfigParser()
        parser.read_string("[DEFAULT]\n" + godot_file.read_text(errors="replace"))
        cfg = dict(parser["DEFAULT"])
        name = cfg.get('config/name', "").strip('"')
        if name:
            result["game_name"] = name
        ver = cfg.get("config_version", "4")
        result["godot_version"] = str(ver)
    except Exception:
        log.exception("Failed to parse project.godot")
    return result


class GameProjectScreen(BaseProjectScreen):
    MODULE_KEY   = "game"
    MODULE_LABEL = "GAME"
    SETUP_FIELDS = [
        {"id": "project_path", "label": "Godot project directory (contains project.godot)",
         "placeholder": "~/projects/my-game", "type": "dir"},
        {"id": "godot_bin", "label": "Godot binary",
         "placeholder": "godot4"},
    ]

    DEFAULT_CSS = _screen_css("GameProjectScreen")

    # ── Setup auto-detection ──────────────────────────────────────────────────

    def on_mount(self) -> None:
        super().on_mount()
        if not self._is_configured():
            self.call_after_refresh(self._autofill_setup)

    def _autofill_setup(self) -> None:
        binary = shutil.which("godot4") or shutil.which("godot")
        try:
            inp = self.query_one("#setup-godot_bin", Input)
            if binary and not inp.value:
                inp.value = binary
        except Exception:
            pass

    # ── Before-save hook ──────────────────────────────────────────────────────

    async def _run_lint(self, project_path: str) -> None:
        from textual.widgets import Log as _Log
        ui_log = self.query_one("#output-log", _Log)
        ui_log.write_line(f"$ gdlint {project_path}")
        try:
            proc = await asyncio.create_subprocess_exec(
                "gdlint", project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            if proc.stdout is None:
                log.error("subprocess stdout is None — cannot stream output")
                return
            errors = warnings = 0
            async for raw in proc.stdout:
                line = raw.decode(errors="replace").rstrip()
                ui_log.write_line(line)
                ll = line.lower()
                if "error" in ll:
                    errors += 1
                elif "warning" in ll:
                    warnings += 1
            await proc.wait()
            icon = "✓" if proc.returncode == 0 else "✗"
            ui_log.write_line(f"\n{icon} {errors} error(s), {warnings} warning(s)")
        except FileNotFoundError:
            ui_log.write_line("✗ gdlint not found.")

    def _on_before_save(self, data: dict) -> dict:
        project_path = Path(data.get("project_path", "")).expanduser()
        godot_bin = data.get("godot_bin", "godot4")
        if not check_binary(godot_bin):
            self.app.notify(
                f"'{godot_bin}' not found — saved anyway. Fix the binary path when it's available.",
                severity="warning",
            )
        return _read_godot_project(project_path)

    # ── Action buttons ────────────────────────────────────────────────────────

    def _compose_action_buttons(self) -> list:
        return [
            Button("Launch Editor",    id="btn-editor",  variant="primary"),
            Button("Run Game",         id="btn-run"),
            Button("Lint (gdtoolkit)", id="btn-lint"),
            Button("Export…",          id="btn-export"),
        ]

    # ── Main content ──────────────────────────────────────────────────────────

    async def _populate_content(self) -> None:
        area = self.query_one("#content-area", Vertical)
        await area.remove_children()

        project_path  = Path(self._mod.get("project_path", "")).expanduser()
        godot_bin     = self._mod.get("godot_bin", "godot4")
        game_name     = self._mod.get("game_name", project_path.name)
        godot_version = self._mod.get("godot_version", "?")

        scene_count = (
            await asyncio.to_thread(lambda: len(list(project_path.rglob("*.tscn"))))
            if project_path.exists() else 0
        )
        bin_found   = shutil.which(godot_bin) is not None

        widgets: list = [
            Horizontal(
                Label("Game:", classes="info-key"),
                Label(game_name, classes="info-val"),
                classes="info-row",
            ),
            Horizontal(
                Label("Godot version:", classes="info-key"),
                Label(godot_version, classes="info-val"),
                classes="info-row",
            ),
            Horizontal(
                Label("Path:", classes="info-key"),
                Label(str(project_path), classes="info-val"),
                classes="info-row",
            ),
            Horizontal(
                Label("Scenes:", classes="info-key"),
                Label(str(scene_count), classes="info-val"),
                classes="info-row",
            ),
            Horizontal(
                Label("Binary:", classes="info-key"),
                Label(
                    f"{godot_bin} ({'found' if bin_found else 'not found on PATH'})",
                    classes="info-val " + ("status-ok" if bin_found else "status-err"),
                ),
                classes="info-row",
            ),
        ]
        await area.mount(*widgets)

    def _primary_folder(self) -> Path | None:
        p = Path(self._mod.get("project_path", "")).expanduser()
        return p if str(p) != "." else None

    # ── Button handler ────────────────────────────────────────────────────────

    def _handle_action(self, bid: str | None) -> None:
        project_path = str(Path(self._mod.get("project_path", "")).expanduser())
        godot_bin    = self._mod.get("godot_bin", "godot4")

        if bid == "btn-editor":
            if not shutil.which(godot_bin):
                self.app.notify(f"'{godot_bin}' not found on PATH.", severity="error")
                return
            self.run_worker(self._run_cmd([godot_bin, "--editor", "--path", project_path]))
        elif bid == "btn-run":
            if not shutil.which(godot_bin):
                self.app.notify(f"'{godot_bin}' not found on PATH.", severity="error")
                return
            self.run_worker(self._run_cmd([godot_bin, "--path", project_path]))
        elif bid == "btn-lint":
            if shutil.which("gdlint"):
                self.run_worker(self._run_lint(project_path))
            else:
                self.app.notify(
                    "gdlint not found. Install gdtoolkit: pip install gdtoolkit",
                    severity="warning",
                )
        elif bid == "btn-export":
            if not shutil.which(godot_bin):
                self.app.notify(f"'{godot_bin}' not found on PATH.", severity="error")
                return
            from nexus.ui.base_project_screen import InputModal
            self.app.push_screen(
                InputModal("Export Game", "Target platform (linux / windows / mac / web):", "linux"),
                lambda platform: self.run_worker(
                    self._run_cmd([godot_bin, "--headless", "--export-release", platform, "--path", project_path])
                ) if platform else None,
            )
