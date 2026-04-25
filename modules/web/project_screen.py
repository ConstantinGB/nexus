from __future__ import annotations
import asyncio
import json
from pathlib import Path

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, Button, Log, Select
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.core.project_manager import ProjectInfo
from nexus.core.platform import open_path
from nexus.ui.base_project_screen import BaseProjectScreen, InputModal, _screen_css


class _ScriptPickerModal(ModalScreen):
    DEFAULT_CSS = """
    _ScriptPickerModal { align: center middle; }
    #sp-dialog {
        background: #2D1B4E; border: solid #00B4FF;
        padding: 1 2; width: 64; height: auto;
    }
    #sp-title  { color: #00B4FF; text-style: bold; height: 2; }
    #sp-select { margin-bottom: 1; }
    #sp-btns   { height: 3; }
    #sp-btns Button { margin-right: 1; }
    """

    def __init__(self, scripts: dict[str, str]) -> None:
        super().__init__()
        self._scripts = scripts

    def compose(self) -> ComposeResult:
        options = [(f"{name}  —  {cmd[:40]}", name) for name, cmd in self._scripts.items()]
        with Vertical(id="sp-dialog"):
            yield Label("Run script:", id="sp-title")
            yield Select(options, id="sp-select", allow_blank=False)
            with Horizontal(id="sp-btns"):
                yield Button("Run ▶", id="sp-ok", variant="primary")
                yield Button("Cancel", id="sp-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "sp-ok":
            val = self.query_one("#sp-select", Select).value
            self.dismiss(val if val is not Select.BLANK else None)
        else:
            self.dismiss(None)

log = get("web.project_screen")

_FRAMEWORK_KEYS = {
    "next": "Next.js",
    "nuxt": "Nuxt",
    "vite": "Vite",
    "@sveltejs/kit": "SvelteKit",
    "svelte": "Svelte",
    "astro": "Astro",
    "remix": "Remix",
    "@angular/core": "Angular",
    "vue": "Vue",
    "react": "React",
}


class WebProjectScreen(BaseProjectScreen):
    MODULE_KEY   = "web"
    MODULE_LABEL = "WEB"
    SETUP_FIELDS = [
        {"id": "project_path", "label": "Web project directory",
         "placeholder": "~/projects/my-site"},
        {"id": "package_manager", "label": "Package manager (npm / pnpm / yarn / bun)",
         "placeholder": "npm"},
    ]

    DEFAULT_CSS = _screen_css("WebProjectScreen")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._running_proc: asyncio.subprocess.Process | None = None

    # ── Before-save hook ──────────────────────────────────────────────────────

    def _on_before_save(self, data: dict) -> dict:
        project_path = Path(data.get("project_path", "")).expanduser()
        pkg_json = project_path / "package.json"
        extra: dict = {"detected_framework": "Unknown", "scripts": {}}
        if pkg_json.exists():
            try:
                info = json.loads(pkg_json.read_text())
                all_deps = {
                    **info.get("dependencies", {}),
                    **info.get("devDependencies", {}),
                }
                for key, name in _FRAMEWORK_KEYS.items():
                    if key in all_deps:
                        extra["detected_framework"] = name
                        break
                extra["scripts"] = info.get("scripts", {})
            except Exception:
                log.exception("Failed to parse package.json")
        return extra

    # ── Action buttons ────────────────────────────────────────────────────────

    def _compose_action_buttons(self) -> list:
        return [
            Button("Dev",      id="btn-dev",      variant="primary"),
            Button("Build",    id="btn-build"),
            Button("Test",     id="btn-test"),
            Button("Lint",     id="btn-lint"),
            Button("Install",      id="btn-install"),
            Button("Run Script…",  id="btn-scripts"),
            Button("■ Stop",       id="btn-stop",     disabled=True),
            Button("Open Dir",     id="btn-open-dir"),
        ]

    # ── Main content ──────────────────────────────────────────────────────────

    async def _populate_content(self) -> None:
        area = self.query_one("#content-area", Vertical)
        await area.remove_children()

        project_path = Path(self._mod.get("project_path", "")).expanduser()
        pm = self._mod.get("package_manager", "npm")
        framework = self._mod.get("detected_framework", "Unknown")
        scripts: dict = self._mod.get("scripts", {})

        widgets: list = [
            Horizontal(
                Label("Framework:", classes="info-key"),
                Label(framework, classes="info-val"),
                classes="info-row",
            ),
            Horizontal(
                Label("Package manager:", classes="info-key"),
                Label(pm, classes="info-val"),
                classes="info-row",
            ),
            Horizontal(
                Label("Path:", classes="info-key"),
                Label(str(project_path), classes="info-val"),
                classes="info-row",
            ),
        ]

        if scripts:
            widgets.append(Label("Scripts:", classes="section-label"))
            for name, cmd in scripts.items():
                widgets.append(
                    Horizontal(
                        Label(f"  {name}", classes="info-key"),
                        Label(cmd, classes="info-val"),
                        classes="info-row",
                    )
                )
        else:
            widgets.append(Label("No package.json found at the configured path.", classes="hint"))

        await area.mount(*widgets)

    # ── Button handler ────────────────────────────────────────────────────────

    def _handle_action(self, bid: str | None) -> None:
        project_path = str(Path(self._mod.get("project_path", "")).expanduser())
        pm = self._mod.get("package_manager", "npm")

        if bid == "btn-dev":
            self.run_worker(self._run_killable([pm, "run", "dev"], cwd=project_path))
        elif bid == "btn-build":
            self.run_worker(self._run_cmd([pm, "run", "build"], cwd=project_path))
        elif bid == "btn-test":
            self.run_worker(self._run_killable([pm, "run", "test"], cwd=project_path))
        elif bid == "btn-lint":
            self.run_worker(self._run_cmd([pm, "run", "lint"], cwd=project_path))
        elif bid == "btn-install":
            self.run_worker(self._run_cmd([pm, "install"], cwd=project_path))
        elif bid == "btn-scripts":
            scripts: dict = self._mod.get("scripts", {})
            if not scripts:
                self.app.notify("No scripts found in package.json.", severity="warning")
                return
            self.app.push_screen(
                _ScriptPickerModal(scripts),
                lambda name: self.run_worker(
                    self._run_killable([pm, "run", name], cwd=project_path)
                ) if name else None,
            )
        elif bid == "btn-stop":
            if self._running_proc:
                self._running_proc.terminate()
                self.app.notify("Process stopped.", severity="information")
        elif bid == "btn-open-dir":
            self.run_worker(self._run_cmd(open_path(project_path)))

    async def _run_killable(self, cmd: list[str], cwd: str | None = None) -> None:
        """Like _run_cmd but tracks the process so Stop can terminate it."""
        ui_log = self.query_one("#output-log", Log)
        btn_stop = self.query_one("#btn-stop", Button)
        ui_log.write_line(f"$ {' '.join(str(c) for c in cmd)}")
        btn_stop.disabled = False
        try:
            proc = await asyncio.create_subprocess_exec(
                *[str(c) for c in cmd],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=cwd,
            )
            self._running_proc = proc
            assert proc.stdout
            async for raw in proc.stdout:
                ui_log.write_line(raw.decode(errors="replace").rstrip())
            await proc.wait()
            ui_log.write_line(f"✓ Exited {proc.returncode}")
        except FileNotFoundError:
            ui_log.write_line(f"✗ Not found: {cmd[0]}")
            self.app.notify(f"'{cmd[0]}' not found on PATH.", severity="error")
        except Exception:
            log.exception("Command failed: %s", cmd)
            ui_log.write_line("✗ Error — see log.")
        finally:
            self._running_proc = None
            btn_stop.disabled = True
