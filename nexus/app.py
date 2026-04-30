from textual.app import App, ComposeResult
from textual.widgets import Header, Footer

from nexus.core.logger import setup as setup_logging, get as get_logger
from nexus.core.platform import read_clipboard, write_clipboard
from nexus.ui.tiles import TileGrid
from nexus.ui.mcp_screen import MCPScreen

log = get_logger("app")


class NexusApp(App):
    TITLE = "NEXUS"
    SUB_TITLE = "Project Manager"
    _docker_containers: set[str] = set()
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("s", "open_settings", "Settings"),
        ("m", "open_mcp", "MCP Servers"),
        ("ctrl+tab", "next_tab", "Next Tab"),
    ]

    def __init__(self, open_project: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._open_project = open_project
        self._tabs: list = []          # list[ProjectInfo]
        self._active_tab_idx: int = -1
        self._going_home_for_new_tab: bool = False

    DEFAULT_CSS = """
    Screen {
        background: #1A0A2E;
    }
    Header {
        background: #2D1B4E;
        color: #00B4FF;
    }
    Footer {
        background: #2D1B4E;
        color: #00FF88;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield TileGrid()
        yield Footer()

    def on_mount(self) -> None:
        from nexus.core.scheduler import BackupScheduler
        self._scheduler = BackupScheduler(self)
        self._scheduler.start()
        if self._open_project:
            self.call_after_refresh(self._auto_open_project)

    def _auto_open_project(self) -> None:
        from nexus.core.project_manager import list_projects
        needle = self._open_project.lower()
        match = next(
            (p for p in list_projects() if p.name.lower().startswith(needle)),
            None,
        )
        if match is None:
            self.notify(f"No project matching '{self._open_project}' found.", severity="warning")
            return
        self.open_project_tab(match)

    def on_unmount(self) -> None:
        if hasattr(self, "_scheduler"):
            self._scheduler.stop()
        import subprocess as _sp
        for name in list(self._docker_containers):
            try:
                _sp.run(
                    ["docker", "stop", "--time=5", name],
                    timeout=8, capture_output=True,
                )
            except Exception as exc:
                log.warning("Failed to stop Docker container %s on exit: %s", name, exc)

    @property
    def clipboard(self) -> str:
        """Read from the OS system clipboard, falling back to Textual's internal buffer."""
        system = read_clipboard()
        if system:
            return system
        return self._clipboard

    def copy_to_clipboard(self, text: str) -> None:
        """Write to both the OS system clipboard and Textual's internal buffer."""
        self._clipboard = text
        write_clipboard(text)

    def action_open_settings(self) -> None:
        from nexus.ui.settings_screen import SettingsScreen
        self.push_screen(SettingsScreen())

    def action_open_mcp(self) -> None:
        self.push_screen(MCPScreen())

    def action_next_tab(self) -> None:
        if len(self._tabs) < 2:
            return
        current = max(0, min(self._active_tab_idx, len(self._tabs) - 1))
        next_idx = (current + 1) % len(self._tabs)
        self.switch_to_tab(self._tabs[next_idx])

    # ── Tab management ────────────────────────────────────────────────────────

    def open_project_tab(self, project) -> None:
        """Open a project as a tab (called from tiles and tab picker)."""
        from nexus.core.module_manager import needs_setup, get_setup_screen, get_project_screen

        self._going_home_for_new_tab = False

        if needs_setup(project):
            screen = get_setup_screen(project)
            if screen:
                self.push_screen(screen)
            return

        existing = next((i for i, t in enumerate(self._tabs) if t.slug == project.slug), None)
        if existing is None:
            self._tabs.append(project)
            self._active_tab_idx = len(self._tabs) - 1
        else:
            self._active_tab_idx = existing

        screen = get_project_screen(project)
        if screen:
            self.push_screen(screen)
        else:
            self.notify(f"No view implemented for '{project.module}' yet.")

    def close_project_tab(self, slug: str) -> None:
        """Remove a project from the tab list (called on screen dismiss)."""
        idx = next((i for i, t in enumerate(self._tabs) if t.slug == slug), None)
        if idx is None:
            return
        self._tabs.pop(idx)
        self._active_tab_idx = min(self._active_tab_idx, len(self._tabs) - 1)

    def switch_to_tab(self, project) -> None:
        """Switch to a different open tab without closing the current tab entry."""
        idx = next((i for i, t in enumerate(self._tabs) if t.slug == project.slug), None)
        if idx is None:
            self._tabs.append(project)
            idx = len(self._tabs) - 1
        self._active_tab_idx = idx

        # Stop terminals and any running server processes on the current screen
        current = self.screen
        try:
            from nexus.ui.terminal_widget import Terminal
            for tid in ("#claude-terminal", "#bash-terminal"):
                try:
                    current.query_one(tid, Terminal).stop()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            proc = getattr(current, "_proc", None)
            if proc is not None and getattr(proc, "returncode", -1) is None:
                proc.terminate()
        except Exception:
            pass

        # Pop current screen (does NOT call close_project_tab — that's for Escape only)
        if len(self.screen_stack) > 1:
            self.pop_screen()

        from nexus.core.module_manager import needs_setup, get_setup_screen, get_project_screen
        if needs_setup(project):
            screen = get_setup_screen(project)
        else:
            screen = get_project_screen(project)
        if screen:
            self.push_screen(screen)


def _register_skills() -> None:
    import nexus.ai.global_skills      # noqa: F401
    import modules.git.skills          # noqa: F401
    import modules.research.skills     # noqa: F401
    import modules.codex.skills        # noqa: F401
    import modules.journal.skills      # noqa: F401
    import modules.org.skills          # noqa: F401
    import modules.web.skills          # noqa: F401
    import modules.game.skills         # noqa: F401
    import modules.home.skills         # noqa: F401
    import modules.streaming.skills    # noqa: F401
    import modules.vtube.skills        # noqa: F401
    import modules.emulator.skills     # noqa: F401
    import modules.vault.skills        # noqa: F401
    import modules.server.skills       # noqa: F401
    import modules.backup.skills       # noqa: F401
    import modules.localai.skills      # noqa: F401
    import modules.sdforge.skills      # noqa: F401
    import modules.custom.skills        # noqa: F401
    import modules.security.skills     # noqa: F401
    import modules.promptopt.skills    # noqa: F401
    import modules.youtube.skills     # noqa: F401
    from nexus.ai.flow_handlers import register_flow_handlers
    register_flow_handlers()
    from nexus.ai.skill_registry import registry
    log.info("Skills registered: %d across scopes %s",
             len(registry.get_tools(registry.all_scopes())),
             sorted(registry.all_scopes()))


def _launch_tui(open_project: str | None = None) -> None:
    setup_logging()
    _register_skills()
    log.info("Starting Nexus UI")
    NexusApp(open_project=open_project).run()
    log.info("Nexus exited cleanly")


def main() -> None:
    import sys, argparse

    parser = argparse.ArgumentParser(
        prog="nexus",
        description="Nexus — personal project organiser",
    )
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("list",    help="List all projects")
    sub.add_parser("version", help="Print version and exit")
    p_open = sub.add_parser("open", help="Launch TUI with a project pre-opened")
    p_open.add_argument("name", help="Project name (case-insensitive prefix match)")

    args = parser.parse_args()

    if args.cmd == "list":
        from nexus.cli import cmd_list
        cmd_list()
        return
    if args.cmd == "version":
        from nexus.cli import cmd_version
        cmd_version()
        return
    if args.cmd == "open":
        _launch_tui(open_project=args.name)
        return

    _launch_tui()
