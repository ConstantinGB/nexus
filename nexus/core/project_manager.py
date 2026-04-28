from __future__ import annotations
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from nexus.core.logger import get

log = get("core.project_manager")

_PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"
_MODULES_DIR  = Path(__file__).parent.parent.parent / "modules"

_DEFAULT_SUBDIRS: dict[str, list[str]] = {
    "research": ["notes"],
    "codex":    ["vault"],
    "journal":  ["journal"],
    "org":      ["plans"],
    "emulator": ["roms"],
}


@dataclass
class ProjectInfo:
    name: str
    slug: str
    module: str
    description: str
    created_at: str
    path: Path


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
        projects.append(ProjectInfo(
            name=cfg.get("name", d.name),
            slug=d.name,
            module=cfg.get("module", ""),
            description=cfg.get("description", ""),
            created_at=cfg.get("created_at", ""),
            path=d,
        ))
    log.debug("Found %d projects", len(projects))
    return projects


def create_project(name: str, module: str, description: str = "") -> ProjectInfo:
    slug = _slugify(name)
    log.info("Creating project: name=%r module=%r slug=%r", name, module, slug)
    if not slug:
        raise ValueError("Project name cannot be empty.")

    project_dir = _PROJECTS_DIR / slug
    if project_dir.exists():
        raise ValueError(f"A project named '{slug}' already exists.")

    try:
        project_dir.mkdir(parents=True)

        cfg = {
            "name": name,
            "module": module,
            "description": description,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mcp": {"servers": {}, "disabled": []},
        }
        with (project_dir / "config.yaml").open("w") as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)

        template = _MODULES_DIR / module / "CLAUDE.template.md"
        claude_md = project_dir / "CLAUDE.md"
        if template.exists() and template.stat().st_size > 0:
            claude_md.write_text(template.read_text())
        else:
            log.debug("No template found for module %r, writing default CLAUDE.md", module)
            claude_md.write_text(f"# {name}\n\nA {module} project managed by Nexus.\n")

        for subdir in _DEFAULT_SUBDIRS.get(module, []):
            (project_dir / subdir).mkdir(exist_ok=True)

        log.info("Project created: %s", slug)
    except Exception:
        log.exception("Failed to create project %r at %s", slug, project_dir)
        if project_dir.exists():
            shutil.rmtree(project_dir, ignore_errors=True)
        raise

    return ProjectInfo(
        name=name,
        slug=slug,
        module=module,
        description=description,
        created_at=cfg["created_at"],
        path=project_dir,
    )


def update_project_meta(slug: str, name: str, description: str) -> None:
    cfg_path = _PROJECTS_DIR / slug / "config.yaml"
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f) or {}
    cfg["name"] = name
    cfg["description"] = description
    with open(cfg_path, "w") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True)
    log.info("Updated project meta: slug=%r name=%r", slug, name)


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
