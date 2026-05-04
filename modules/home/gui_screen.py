from __future__ import annotations

from nexus.core.project_manager import ProjectInfo
from nexus.ui.gui.module_base import ModuleGuiBase

log = __import__("nexus.core.logger", fromlist=["get"]).get("home.gui_screen")


class GuiScreen(ModuleGuiBase):
    SKILL_SCOPES = ["global", "home"]

    def __init__(self, project: ProjectInfo, parent=None) -> None:
        super().__init__(project, parent)
        self.setWindowTitle(f"Home Assistant — {project.name}")
        self._mod = self._cfg.get("home", {})
        self._populate()

    def _build_toolbar(self) -> None:
        self._add_btn("Ping HA",         self._do_ping,         primary=True)
        self._add_btn("Check API",        self._do_check_api)
        self._add_btn("Open Config Dir",  self._do_open_config)
        self._add_btn("Open in Browser",  self._do_open_browser)

    def _populate(self) -> None:
        m = self._mod
        url   = m.get("ha_url", "")
        token = m.get("token", "")
        self._set_info([
            ("HA URL", url or "(not set)"),
            ("Token",  "configured" if token else "(not set)"),
        ])

    # ── Actions ───────────────────────────────────────────────────────────────

    def _do_ping(self) -> None:
        url = self._mod.get("ha_url", "")
        if not url:
            self._append("[error] HA URL not configured.")
            return
        import urllib.parse
        host = urllib.parse.urlparse(url).hostname or url
        self._run_cmd(["ping", "-c", "4", host])

    def _do_check_api(self) -> None:
        url   = self._mod.get("ha_url", "")
        token = self._mod.get("token", "")
        if not url or not token:
            self._append("[error] HA URL and token required.")
            return
        self._run_cmd(["curl", "-s", "-H", f"Authorization: Bearer {token}",
                        f"{url.rstrip('/')}/api/"])

    def _do_open_config(self) -> None:
        d = self._mod.get("config_dir", "")
        if d:
            from nexus.core.platform import open_path
            open_path(d)
        else:
            self._append("[info] Config dir not set.")

    def _do_open_browser(self) -> None:
        url = self._mod.get("ha_url", "")
        if url:
            import webbrowser
            webbrowser.open(url)
