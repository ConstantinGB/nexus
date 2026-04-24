from __future__ import annotations
from pathlib import Path

from textual.widgets import Label, Button, Log
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.ui.base_project_screen import BaseProjectScreen, InputModal, _screen_css

log = get("emulator.project_screen")


def _count_roms(system_dir: Path) -> int:
    try:
        return sum(1 for f in system_dir.iterdir() if f.is_file())
    except Exception:
        return 0


class EmulatorProjectScreen(BaseProjectScreen):
    MODULE_KEY   = "emulator"
    MODULE_LABEL = "EMULATOR"
    SETUP_FIELDS = [
        {"id": "rom_dir",       "label": "ROM directory",
         "placeholder": "~/Roms"},
        {"id": "retroarch_bin", "label": "RetroArch binary",
         "placeholder": "retroarch"},
    ]

    DEFAULT_CSS = _screen_css("EmulatorProjectScreen") + """
    .system-row      { height: 1; }
    .system-name     { color: #E0E0FF; width: 22; }
    .system-count    { color: #8080AA; width: 10; }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._detected_systems: list[str] = []

    # ── Action buttons ────────────────────────────────────────────────────────

    def _compose_action_buttons(self) -> list:
        return [
            Button("Launch RetroArch",  id="btn-launch-ra",     variant="primary"),
            Button("Browse by System",  id="btn-browse-system"),
            Button("Open ROM Dir",      id="btn-open-rom-dir"),
        ]

    # ── Main content ──────────────────────────────────────────────────────────

    async def _populate_content(self) -> None:
        area = self.query_one("#content-area", Vertical)
        await area.remove_children()

        rom_dir       = Path(self._mod.get("rom_dir", "")).expanduser()
        retroarch_bin = self._mod.get("retroarch_bin", "retroarch")

        widgets: list = [
            Horizontal(
                Label("ROM dir:", classes="info-key"),
                Label(str(rom_dir), classes="info-val"),
                classes="info-row",
            ),
            Horizontal(
                Label("RetroArch:", classes="info-key"),
                Label(retroarch_bin, classes="info-val"),
                classes="info-row",
            ),
        ]

        if rom_dir.exists():
            systems = sorted(d for d in rom_dir.iterdir() if d.is_dir())
            self._detected_systems = [s.name for s in systems]
            widgets.append(
                Horizontal(
                    Label("Systems:", classes="info-key"),
                    Label(str(len(systems)), classes="info-val"),
                    classes="info-row",
                )
            )
            widgets.append(Label("ROM library:", classes="section-label"))
            for system in systems:
                count = _count_roms(system)
                widgets.append(
                    Horizontal(
                        Label(system.name, classes="system-name"),
                        Label(f"{count} ROMs", classes="system-count"),
                        classes="system-row",
                    )
                )
        else:
            self._detected_systems = []
            widgets.append(Label(f"ROM directory not found: {rom_dir}", classes="status-err"))
            widgets.append(Label("Create the directory and add system subdirectories.", classes="hint"))

        await area.mount(*widgets)

    # ── Button handler ────────────────────────────────────────────────────────

    def _handle_action(self, bid: str | None) -> None:
        rom_dir       = Path(self._mod.get("rom_dir", "")).expanduser()
        retroarch_bin = self._mod.get("retroarch_bin", "retroarch")

        if bid == "btn-launch-ra":
            self.run_worker(self._run_cmd([retroarch_bin]))

        elif bid == "btn-browse-system":
            if not self._detected_systems:
                self.app.notify("No systems detected. Check your ROM directory.", severity="warning")
                return
            systems_str = " / ".join(self._detected_systems[:10])
            prompt = f"Systems: {systems_str}"
            if len(self._detected_systems) > 10:
                prompt += f" (+{len(self._detected_systems) - 10} more)"
            self.app.push_screen(
                InputModal("Browse by System", prompt, self._detected_systems[0]),
                lambda system: self._launch_system(system, rom_dir, retroarch_bin),
            )

        elif bid == "btn-open-rom-dir":
            self.run_worker(self._run_cmd(["xdg-open", str(rom_dir)]))

    def _launch_system(self, system: str | None, rom_dir: Path, retroarch_bin: str) -> None:
        if not system:
            return
        system_dir = rom_dir / system
        if not system_dir.exists():
            self.app.notify(f"System directory not found: {system}", severity="warning")
            return
        self.run_worker(
            self._run_cmd([retroarch_bin, "--contentdir", str(system_dir)])
        )
