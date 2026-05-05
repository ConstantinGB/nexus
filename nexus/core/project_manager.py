from __future__ import annotations
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

from nexus.core.logger import get

log = get("core.project_manager")

_PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"
_MODULES_DIR  = Path(__file__).parent.parent.parent / "modules"

_DEFAULT_SUBDIRS: dict[str, list[str]] = {
    "research": ["notes"],
    "codex":    ["codex"],
    "journal":  ["journal"],
    "org":      ["plans"],
    "emulator": ["roms"],
    "calendar": ["data/calendar"],
    "notes":    ["data/notes"],
    "tasks":    ["data/todo"],
}


def ensure_module_dirs(project_path: Path, module_id: str) -> None:
    """Create the standard subdirectories for *module_id* under *project_path*."""
    for subdir in _DEFAULT_SUBDIRS.get(module_id, []):
        (project_path / subdir).mkdir(parents=True, exist_ok=True)


@dataclass
class ProjectInfo:
    name: str
    slug: str
    modules: list[str]   # canonical — replaces module
    description: str
    created_at: str
    path: Path

    @property
    def module(self) -> str:
        return self.modules[0] if self.modules else ""


def _slugify(name: str) -> str:
    import re
    slug = re.sub(r"[^a-z0-9-]", "-", name.lower().strip())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "project"


def list_projects() -> list[ProjectInfo]:
    log.debug("Listing projects under %s", _PROJECTS_DIR)
    if not _PROJECTS_DIR.exists():
        log.warning("Projects directory does not exist: %s", _PROJECTS_DIR)
        return []
    projects = []
    for d in sorted(_PROJECTS_DIR.iterdir()):
        if not d.is_dir():
            continue
        cfg_path = d / "config.yaml"
        if not cfg_path.exists():
            continue
        try:
            with cfg_path.open() as f:
                cfg = yaml.safe_load(f) or {}
        except Exception:
            log.exception("Failed to read config for project dir: %s", d.name)
            continue
        # Handle both 'modules' (new) and 'module' (old) config keys
        raw_modules = cfg.get("modules") or ([cfg["module"]] if cfg.get("module") else [])
        custom_path_str = cfg.get("custom_path", "")
        effective_path = Path(custom_path_str).expanduser() if custom_path_str else d
        projects.append(ProjectInfo(
            name=cfg.get("name", d.name),
            slug=d.name,
            modules=raw_modules,
            description=cfg.get("description", ""),
            created_at=cfg.get("created_at", ""),
            path=effective_path,
        ))
    log.debug("Found %d projects", len(projects))
    return projects


def create_project(name: str, modules: list[str], description: str = "") -> ProjectInfo:
    slug = _slugify(name)
    log.info("Creating project: name=%r modules=%r slug=%r", name, modules, slug)
    if not slug:
        raise ValueError("Project name cannot be empty.")

    project_dir = _PROJECTS_DIR / slug
    try:
        project_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise ValueError(f"A project named '{slug}' already exists.")

    try:
        cfg = {
            "name": name,
            "modules": modules,
            "description": description,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mcp": {"servers": {}, "disabled": []},
        }
        with (project_dir / "config.yaml").open("w") as f:
            yaml.safe_dump(cfg, f, default_flow_style=False, allow_unicode=True)

        # Copy CLAUDE.template.md from the first module that has one
        claude_written = False
        for module in modules:
            template = _MODULES_DIR / module / "CLAUDE.template.md"
            if template.exists() and template.stat().st_size > 0:
                (project_dir / "CLAUDE.md").write_text(template.read_text())
                claude_written = True
                break
        if not claude_written:
            first_module = modules[0] if modules else "custom"
            log.debug("No template found for modules %r, writing default CLAUDE.md", modules)
            (project_dir / "CLAUDE.md").write_text(
                f"# {name}\n\nA project managed by Nexus.\n"
            )

        # Create subdirs for ALL modules in the list
        for module in modules:
            ensure_module_dirs(project_dir, module)

        log.info("Project created: %s", slug)
    except Exception:
        log.exception("Failed to create project %r at %s", slug, project_dir)
        if project_dir.exists():
            shutil.rmtree(project_dir, ignore_errors=True)
        raise

    return ProjectInfo(
        name=name,
        slug=slug,
        modules=modules,
        description=description,
        created_at=cfg["created_at"],
        path=project_dir,
    )


def update_project_meta(slug: str, name: str, description: str) -> None:
    cfg_path = _PROJECTS_DIR / slug / "config.yaml"
    try:
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f) or {}
        cfg["name"] = name
        cfg["description"] = description
        with open(cfg_path, "w") as f:
            yaml.safe_dump(cfg, f, allow_unicode=True)
        log.info("Updated project meta: slug=%r name=%r", slug, name)
    except OSError:
        log.exception("Failed to update project meta for slug=%r", slug)
        raise


def update_project_modules(slug: str, modules: list[str]) -> None:
    cfg_path = _PROJECTS_DIR / slug / "config.yaml"
    try:
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f) or {}
        cfg["modules"] = modules
        with open(cfg_path, "w") as f:
            yaml.safe_dump(cfg, f, allow_unicode=True)
        log.info("Updated project modules: slug=%r modules=%r", slug, modules)
    except OSError:
        log.exception("Failed to update modules for slug=%r", slug)
        raise


def update_project_path(slug: str, new_path: Path) -> None:
    """Record *new_path* as custom_path in config without moving any files."""
    cfg_path = _PROJECTS_DIR / slug / "config.yaml"
    try:
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f) or {}
        if new_path:
            cfg["custom_path"] = str(new_path.expanduser())
        else:
            cfg.pop("custom_path", None)
        with open(cfg_path, "w") as f:
            yaml.safe_dump(cfg, f, allow_unicode=True)
        log.info("Updated custom_path for slug=%r → %s", slug, new_path)
    except OSError:
        log.exception("Failed to update custom_path for slug=%r", slug)
        raise


def move_project_files(slug: str, new_path: Path) -> None:
    """Move the project's data directory to *new_path* and update config."""
    cfg_path = _PROJECTS_DIR / slug / "config.yaml"
    try:
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f) or {}
    except OSError:
        log.exception("Cannot read config for slug=%r", slug)
        raise

    old_custom = cfg.get("custom_path", "")
    old_data = Path(old_custom).expanduser() if old_custom else _PROJECTS_DIR / slug
    new_data = new_path.expanduser()

    if old_data.resolve() == new_data.resolve():
        return

    new_data.mkdir(parents=True, exist_ok=True)
    try:
        for item in old_data.iterdir():
            # config.yaml stays in projects/<slug>/ when moving from the default location
            if old_data == _PROJECTS_DIR / slug and item.name == "config.yaml":
                continue
            dest = new_data / item.name
            shutil.move(str(item), str(dest))
    except Exception:
        log.exception("Failed to move project files from %s to %s", old_data, new_data)
        raise

    try:
        cfg["custom_path"] = str(new_data)
        with open(cfg_path, "w") as f:
            yaml.safe_dump(cfg, f, allow_unicode=True)
        log.info("Moved project %r from %s to %s", slug, old_data, new_data)
    except OSError:
        log.exception("Moved files but failed to update config for slug=%r", slug)
        raise


def delete_project(slug: str) -> None:
    log.info("Deleting project: %s", slug)
    project_dir = _PROJECTS_DIR / slug
    if not project_dir.exists():
        raise ValueError(f"No project found with slug '{slug}'.")
    try:
        shutil.rmtree(project_dir)
        log.info("Project deleted: %s", slug)
    except Exception:
        log.exception("Failed to delete project: %s", slug)
        raise
