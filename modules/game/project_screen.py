from __future__ import annotations
import configparser
import shutil
from pathlib import Path

from textual.widgets import Label, Button, Log
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
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
         "placeholder": "~/projects/my-game"},
        {"id": "godot_bin", "label": "Godot binary",
         "placeholder": "godot4"},
    ]

    DEFAULT_CSS = _screen_css("GameProjectScreen")

    # ── Before-save hook ──────────────────────────────────────────────────────

    def _on_before_save(self, data: dict) -> dict:
        project_path = Path(data.get("project_path", "")).expanduser()
        return _read_godot_project(project_path)

    # ── Action buttons ────────────────────────────────────────────────────────

    def _compose_action_buttons(self) -> list:
        return [
            Button("Launch Editor", id="btn-editor",  variant="primary"),
            Button("Run Game",      id="btn-run"),
            Button("Lint (gdtoolkit)", id="btn-lint"),
        ]

    # ── Main content ──────────────────────────────────────────────────────────

    async def _populate_content(self) -> None:
        area = self.query_one("#content-area", Vertical)
        await area.remove_children()

        project_path  = Path(self._mod.get("project_path", "")).expanduser()
        godot_bin     = self._mod.get("godot_bin", "godot4")
        game_name     = self._mod.get("game_name", project_path.name)
        godot_version = self._mod.get("godot_version", "?")

        scene_count = len(list(project_path.rglob("*.tscn"))) if project_path.exists() else 0
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

    # ── Button handler ────────────────────────────────────────────────────────

    def _handle_action(self, bid: str | None) -> None:
        project_path = str(Path(self._mod.get("project_path", "")).expanduser())
        godot_bin    = self._mod.get("godot_bin", "godot4")

        if bid == "btn-editor":
            self.run_worker(self._run_cmd([godot_bin, "--editor", "--path", project_path]))
        elif bid == "btn-run":
            self.run_worker(self._run_cmd([godot_bin, "--path", project_path]))
        elif bid == "btn-lint":
            if shutil.which("gdlint"):
                self.run_worker(self._run_cmd(["gdlint", project_path]))
            else:
                self.app.notify(
                    "gdlint not found. Install gdtoolkit: pip install gdtoolkit",
                    severity="warning",
                )
