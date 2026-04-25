from textual.app import App, ComposeResult
from textual.widgets import Header, Footer

from nexus.core.logger import setup as setup_logging, get as get_logger
from nexus.ui.tiles import TileGrid
from nexus.ui.mcp_screen import MCPScreen

log = get_logger("app")


class NexusApp(App):
    TITLE = "NEXUS"
    SUB_TITLE = "Project Manager"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("s", "open_settings", "Settings"),
        ("m", "open_mcp", "MCP Servers"),
    ]

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

    def on_unmount(self) -> None:
        if hasattr(self, "_scheduler"):
            self._scheduler.stop()

    def action_open_settings(self) -> None:
        from nexus.ui.settings_screen import SettingsScreen
        self.push_screen(SettingsScreen())

    def action_open_mcp(self) -> None:
        self.push_screen(MCPScreen())


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
    import modules.custom.skills       # noqa: F401
    from nexus.ai.flow_handlers import register_flow_handlers
    register_flow_handlers()
    from nexus.ai.skill_registry import registry
    log.info("Skills registered: %d across scopes %s",
             len(registry.get_tools(registry.all_scopes())),
             sorted(registry.all_scopes()))


def main() -> None:
    setup_logging()
    _register_skills()
    log.info("Starting Nexus UI")
    NexusApp().run()
    log.info("Nexus exited cleanly")
