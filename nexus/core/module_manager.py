from __future__ import annotations
import importlib
import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Root of the modules/ directory, resolved relative to this file.
_MODULES_ROOT   = Path(__file__).parent.parent.parent / "modules"
_PROJECTS_ROOT  = Path(__file__).parent.parent.parent / "projects"


@dataclass
class ModuleInfo:
    id: str
    name: str
    description: str
    tags: list[str] = field(default_factory=list)
    system: bool = False
    mode_aware: bool = False


def _load_registry() -> tuple[list[ModuleInfo], dict[str, str], dict[str, dict]]:
    """Scan modules/*/module.toml and build registry, prefix map, and raw meta map."""
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-reattr]

    registry: list[ModuleInfo] = []
    prefix_map: dict[str, str] = {}
    meta_map: dict[str, dict] = {}

    for toml_path in sorted(_MODULES_ROOT.glob("*/module.toml")):
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
        mod = data["module"]
        info = ModuleInfo(
            id=mod["id"],
            name=mod["label"],
            description=mod["description"],
            tags=mod.get("tags", []),
            system=mod.get("system", False),
            mode_aware=mod.get("mode_aware", False),
        )
        registry.append(info)
        prefix_map[mod["id"]] = mod.get("prefix", mod["id"][:3])
        meta_map[mod["id"]] = data  # full toml, including [setup] if present

    return registry, prefix_map, meta_map


_REGISTRY, MODULE_PREFIX, _META = _load_registry()
_REGISTRY_BY_ID: dict[str, ModuleInfo] = {m.id: m for m in _REGISTRY}


def list_modules() -> list[ModuleInfo]:
    return list(_REGISTRY)


def list_feature_modules() -> list[ModuleInfo]:
    return [m for m in _REGISTRY if not m.system]


def list_system_modules() -> list[ModuleInfo]:
    return [m for m in _REGISTRY if m.system]


def is_system_module(module_id: str) -> bool:
    m = _REGISTRY_BY_ID.get(module_id)
    return bool(m and m.system)


def is_mode_aware_module(module_id: str) -> bool:
    m = _REGISTRY_BY_ID.get(module_id)
    return bool(m and m.mode_aware)


def get_module(module_id: str) -> ModuleInfo | None:
    return _REGISTRY_BY_ID.get(module_id)


def _resolve_config_key(cfg: dict, dot_path: str) -> object:
    """Follow a dot-separated path into a nested dict, returning None if missing."""
    parts = dot_path.split(".")
    val: object = cfg
    for part in parts:
        if not isinstance(val, dict):
            return None
        val = val.get(part)
    return val


def needs_setup(project) -> bool:
    """Return True if ANY module in the project hasn't been configured yet."""
    for mid in project.modules:
        setup = _META.get(mid, {}).get("setup", {})
        config_check = setup.get("config_check")
        if not config_check:
            continue
        from nexus.core.config_manager import load_project_config
        cfg = load_project_config(project.slug)
        if not bool(_resolve_config_key(cfg, config_check)):
            return True
    return False


def needs_setup_for_module(project, module_id: str) -> bool:
    """Return True if a specific module in the project needs setup."""
    setup = _META.get(module_id, {}).get("setup", {})
    config_check = setup.get("config_check")
    if not config_check:
        return False
    from nexus.core.config_manager import load_project_config
    cfg = load_project_config(project.slug)
    return not bool(_resolve_config_key(cfg, config_check))


def get_setup_screen(project):
    """Return the setup Screen instance for the FIRST unconfigured module that needs one."""
    for mid in project.modules:
        if needs_setup_for_module(project, mid):
            screen = get_setup_screen_for_module(project, mid)
            if screen:
                return screen
    return None


def get_setup_screen_for_module(project, module_id: str):
    """Return the setup Screen instance for a specific module, or None."""
    setup = _META.get(module_id, {}).get("setup", {})

    if setup.get("has_setup_screen"):
        mod = importlib.import_module(f"modules.{module_id}.setup_screen")
        return mod.SetupScreen(project)

    if setup.get("use_project_screen"):
        mod = importlib.import_module(f"modules.{module_id}.project_screen")
        return mod.ProjectScreen(project)

    return None


def get_project_screen(project):
    """Return the main Screen instance for an already-configured project, or None.

    Returns the ProjectHubScreen for multi-module projects, or the single module
    screen for single-module projects (for backward compat with legacy projects).

    Checks projects/<slug>/screen.py first — if it exists and defines ProjectScreen,
    that per-project override is used instead of the module default.
    """
    local = _PROJECTS_ROOT / project.slug / "screen.py"
    if local.exists():
        try:
            spec = importlib.util.spec_from_file_location(
                f"_project_screen_{project.slug}", local
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            cls = getattr(mod, "ProjectScreen", None)
            if cls is not None:
                return cls(project)
        except Exception:
            import logging
            logging.getLogger("nexus.module_manager").exception(
                "Failed to load per-project screen for %s — falling back to module default",
                project.slug,
            )

    # Use hub screen for all projects (handles both single and multi-module)
    try:
        from nexus.ui.tui.project_hub_screen import ProjectHubScreen
        return ProjectHubScreen(project)
    except Exception:
        import logging
        logging.getLogger("nexus.module_manager").exception(
            "Failed to load ProjectHubScreen for %s — falling back to first module screen",
            project.slug,
        )

    # Fallback: first module screen
    if not project.modules:
        return None
    return get_project_screen_for_module(project, project.modules[0])


def get_project_screen_for_module(project, module_id: str):
    """Load ProjectScreen for a specific module in a multi-module project."""
    try:
        mod = importlib.import_module(f"modules.{module_id}.project_screen")
        cls = getattr(mod, "ProjectScreen", None)
        return cls(project) if cls else None
    except Exception:
        return None
