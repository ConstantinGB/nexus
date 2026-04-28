from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ModuleInfo:
    id: str
    name: str
    description: str
    tags: list[str] = field(default_factory=list)
    system: bool = False


_REGISTRY: list[ModuleInfo] = [
    ModuleInfo("git",      "Git",      "Manage Git repositories — GitHub, self-hosted, or local.",             ["dev", "vcs"]),
    ModuleInfo("web",      "Web",      "Set up a web development environment with browser testing.",           ["dev", "web"]),
    ModuleInfo("research", "Research", "AI-assisted research: web scraping, search engines, Wikipedia.",       ["ai", "research"]),
    ModuleInfo("codex",    "Codex",    "Persistent knowledge base — store and categorize what you've learned.",["ai", "knowledge"]),
    ModuleInfo("journal",  "Journal",  "Write and read a personal journal, formatted with LaTeX.",             ["writing"]),
    ModuleInfo("server",   "Server",   "Spin up local servers: Minecraft, web server, mail server, and more.",["server", "hosting"]),
    ModuleInfo("home",     "Home",     "Home Assistant setup and automation management.",                      ["iot", "home"]),
    ModuleInfo("game",     "Game",     "Godot game development environment.",                                  ["dev", "game"]),
    ModuleInfo("org",      "Org",      "Organize with timetables, diagrams, and workflows.",                   ["planning"]),
    ModuleInfo("custom",    "Custom",    "A blank project. Write your own description for the AI to work from.",          []),
    ModuleInfo("localai",   "LocalAI",   "Set up and run local AI models — LLMs, diffusion, audio, and more.",           ["ai", "local"],    system=True),
    ModuleInfo("sdforge",   "SDForge",   "Stable Diffusion Forge — local image generation via A1111-compatible API.",     ["ai", "image", "local"], system=True),
    ModuleInfo("streaming", "Streaming", "OBS-based live streaming and recording setup.",                                 ["media", "obs"]),
    ModuleInfo("vtube",     "VTube",     "Virtual avatar setup — face tracking, Live2D/VRM models, OBS integration.",    ["media", "avatar"]),
    ModuleInfo("emulator",  "Emulator",  "Retro console emulation — RetroArch, Dolphin, PCSX2, RPCS3, and more.",       ["gaming", "retro"]),
    ModuleInfo("vault",     "Vault",     "Encrypted file storage and secrets management — GPG, VeraCrypt, KeePassXC.",   ["security", "crypto"]),
    ModuleInfo("backup",    "Backup",    "Encrypted, deduplicated backups via restic — local, NAS (SFTP), or NFS.",      ["system", "backup"], system=True),
    ModuleInfo("security",  "Security",  "Firewall, VPN, DNS privacy and system hardening.",                              ["security", "privacy", "network"]),
]

_REGISTRY_BY_ID: dict[str, ModuleInfo] = {m.id: m for m in _REGISTRY}

MODULE_PREFIX: dict[str, str] = {
    "research": "res",
    "journal":  "jnl",
    "codex":    "cod",
    "git":      "git",
    "localai":  "loc",
    "web":      "web",
    "game":     "gam",
    "org":      "org",
    "home":     "hom",
    "streaming":"str",
    "vtube":    "vtu",
    "emulator": "emu",
    "vault":    "vlt",
    "server":   "srv",
    "custom":   "cst",
    "backup":   "bak",
    "sdforge":  "sdf",
    "security": "sec",
}


def list_modules() -> list[ModuleInfo]:
    return list(_REGISTRY)


def list_system_modules() -> list[ModuleInfo]:
    return [m for m in _REGISTRY if m.system]


def get_module(module_id: str) -> ModuleInfo | None:
    return _REGISTRY_BY_ID.get(module_id)


def needs_setup(project) -> bool:
    """Return True if the project hasn't been configured yet."""
    from nexus.core.config_manager import load_project_config
    if project.module == "git":
        cfg = load_project_config(project.slug)
        return "git" not in cfg or not cfg.get("git", {}).get("type")
    if project.module == "localai":
        cfg = load_project_config(project.slug)
        return not cfg.get("localai", {}).get("setup_done", False)
    if project.module == "backup":
        cfg = load_project_config(project.slug)
        return not cfg.get("backup", {}).get("setup_done", False)
    if project.module == "sdforge":
        cfg = load_project_config(project.slug)
        return not cfg.get("sdforge", {}).get("setup_done", False)
    return False


def get_setup_screen(project):
    """Return the setup Screen instance for a project's module, or None."""
    if project.module == "git":
        from modules.git.setup_screen import GitSetupScreen
        return GitSetupScreen(project)
    if project.module == "localai":
        from modules.localai.setup_screen import LocalAISetupScreen
        return LocalAISetupScreen(project)
    if project.module == "backup":
        from modules.backup.setup_screen import BackupSetupScreen
        return BackupSetupScreen(project)
    if project.module == "sdforge":
        from modules.sdforge.setup_screen import SDForgeSetupScreen
        return SDForgeSetupScreen(project)
    return None


def get_project_screen(project):
    """Return the main Screen instance for an already-configured project, or None."""
    if project.module == "git":
        from modules.git.project_screen import GitProjectScreen
        return GitProjectScreen(project)
    if project.module == "localai":
        from modules.localai.project_screen import LocalAIProjectScreen
        return LocalAIProjectScreen(project)
    if project.module == "web":
        from modules.web.project_screen import WebProjectScreen
        return WebProjectScreen(project)
    if project.module == "research":
        from modules.research.project_screen import ResearchProjectScreen
        return ResearchProjectScreen(project)
    if project.module == "codex":
        from modules.codex.project_screen import CodexProjectScreen
        return CodexProjectScreen(project)
    if project.module == "journal":
        from modules.journal.project_screen import JournalProjectScreen
        return JournalProjectScreen(project)
    if project.module == "game":
        from modules.game.project_screen import GameProjectScreen
        return GameProjectScreen(project)
    if project.module == "org":
        from modules.org.project_screen import OrgProjectScreen
        return OrgProjectScreen(project)
    if project.module == "home":
        from modules.home.project_screen import HomeProjectScreen
        return HomeProjectScreen(project)
    if project.module == "streaming":
        from modules.streaming.project_screen import StreamingProjectScreen
        return StreamingProjectScreen(project)
    if project.module == "vtube":
        from modules.vtube.project_screen import VTubeProjectScreen
        return VTubeProjectScreen(project)
    if project.module == "emulator":
        from modules.emulator.project_screen import EmulatorProjectScreen
        return EmulatorProjectScreen(project)
    if project.module == "vault":
        from modules.vault.project_screen import VaultProjectScreen
        return VaultProjectScreen(project)
    if project.module == "server":
        from modules.server.project_screen import ServerProjectScreen
        return ServerProjectScreen(project)
    if project.module == "backup":
        from modules.backup.project_screen import BackupProjectScreen
        return BackupProjectScreen(project)
    if project.module == "sdforge":
        from modules.sdforge.project_screen import SDForgeProjectScreen
        return SDForgeProjectScreen(project)
    if project.module == "custom":
        from modules.custom.project_screen import CustomProjectScreen
        return CustomProjectScreen(project)
    if project.module == "security":
        from modules.security.project_screen import SecurityProjectScreen
        return SecurityProjectScreen(project)
    return None
