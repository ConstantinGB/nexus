from __future__ import annotations
import json
from pathlib import Path

from textual.app import ComposeResult
from textual.widgets import Label, Button, Log
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.core.project_manager import ProjectInfo
from nexus.ui.base_project_screen import BaseProjectScreen, InputModal, _screen_css

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
            Button("Open Dir", id="btn-open-dir"),
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
            self.run_worker(self._run_cmd([pm, "run", "dev"], cwd=project_path))
        elif bid == "btn-build":
            self.run_worker(self._run_cmd([pm, "run", "build"], cwd=project_path))
        elif bid == "btn-test":
            self.run_worker(self._run_cmd([pm, "run", "test"], cwd=project_path))
        elif bid == "btn-lint":
            self.run_worker(self._run_cmd([pm, "run", "lint"], cwd=project_path))
        elif bid == "btn-open-dir":
            self.run_worker(self._run_cmd(["xdg-open", project_path]))
