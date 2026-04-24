from __future__ import annotations
import json
from pathlib import Path

from nexus.ai.skill_registry import registry
from nexus.core.config_manager import load_project_config, save_project_config
from nexus.core.logger import get

log = get("skills.git")

_PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"


def _repo_path(slug: str, mod: dict, repo_name: str) -> Path | None:
    repos = mod.get("repos", [])
    meta  = next((r for r in repos if r["name"] == repo_name), None)
    base  = _PROJECTS_DIR / slug
    if meta:
        return base / meta.get("path", f"repos/{repo_name}")
    candidate = base / "repos" / repo_name
    return candidate if candidate.exists() else None


def _load(slug: str) -> dict:
    return load_project_config(slug).get("git", {})


# ---------------------------------------------------------------------------
# git_status
# ---------------------------------------------------------------------------

async def _git_status(args: dict) -> str:
    slug = args["project_slug"]
    repo = args["repo"]
    mod  = _load(slug)
    path = _repo_path(slug, mod, repo)
    if path is None:
        return json.dumps({"error": f"Repo '{repo}' not found in project '{slug}'"})
    try:
        from modules.git.git_ops import get_repo_status, get_recent_commits
        status  = get_repo_status(path)
        commits = get_recent_commits(path, n=5)
        return json.dumps({"status": status, "recent_commits": commits})
    except Exception as exc:
        log.exception("git_status skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "git",
    name        = "git_status",
    description = "Get the current branch, ahead/behind counts, dirty flag, and last 5 commits for a repository.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string", "description": "Nexus project slug"},
            "repo":         {"type": "string", "description": "Repository directory name"},
        },
        "required": ["project_slug", "repo"],
    },
    handler = _git_status,
)


# ---------------------------------------------------------------------------
# git_pull
# ---------------------------------------------------------------------------

async def _git_pull(args: dict) -> str:
    slug = args["project_slug"]
    repo = args["repo"]
    mod  = _load(slug)
    path = _repo_path(slug, mod, repo)
    if path is None:
        return json.dumps({"error": f"Repo '{repo}' not found in project '{slug}'"})
    try:
        from modules.git.git_ops import pull_repo
        ok, msg = pull_repo(path)
        return json.dumps({"success": ok, "message": msg})
    except Exception as exc:
        log.exception("git_pull skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "git",
    name        = "git_pull",
    description = "Pull the latest commits for a named repository.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "repo":         {"type": "string", "description": "Repository directory name"},
        },
        "required": ["project_slug", "repo"],
    },
    handler = _git_pull,
)


# ---------------------------------------------------------------------------
# git_push
# ---------------------------------------------------------------------------

async def _git_push(args: dict) -> str:
    slug = args["project_slug"]
    repo = args["repo"]
    mod  = _load(slug)
    path = _repo_path(slug, mod, repo)
    if path is None:
        return json.dumps({"error": f"Repo '{repo}' not found in project '{slug}'"})
    try:
        from modules.git.git_ops import push_repo
        ok, msg = push_repo(path)
        return json.dumps({"success": ok, "message": msg})
    except Exception as exc:
        log.exception("git_push skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "git",
    name        = "git_push",
    description = "Push local commits to the remote for a named repository.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "repo":         {"type": "string"},
        },
        "required": ["project_slug", "repo"],
    },
    handler = _git_push,
)


# ---------------------------------------------------------------------------
# git_commit
# ---------------------------------------------------------------------------

async def _git_commit(args: dict) -> str:
    slug    = args["project_slug"]
    repo    = args["repo"]
    message = args["message"]
    mod     = _load(slug)
    path    = _repo_path(slug, mod, repo)
    if path is None:
        return json.dumps({"error": f"Repo '{repo}' not found in project '{slug}'"})
    try:
        from modules.git.git_ops import commit_and_push
        ok, msg = commit_and_push(path, message)
        return json.dumps({"success": ok, "message": msg})
    except Exception as exc:
        log.exception("git_commit skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "git",
    name        = "git_commit",
    description = "Stage all changes, commit with a message, and push to remote.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "repo":         {"type": "string"},
            "message":      {"type": "string", "description": "Commit message"},
        },
        "required": ["project_slug", "repo", "message"],
    },
    handler = _git_commit,
)


# ---------------------------------------------------------------------------
# git_log
# ---------------------------------------------------------------------------

async def _git_log(args: dict) -> str:
    slug = args["project_slug"]
    repo = args["repo"]
    n    = int(args.get("n", 10))
    mod  = _load(slug)
    path = _repo_path(slug, mod, repo)
    if path is None:
        return json.dumps({"error": f"Repo '{repo}' not found in project '{slug}'"})
    try:
        from modules.git.git_ops import get_recent_commits
        commits = get_recent_commits(path, n=n)
        return json.dumps({"commits": commits})
    except Exception as exc:
        log.exception("git_log skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "git",
    name        = "git_log",
    description = "Return recent commit history for a repository.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "repo":         {"type": "string"},
            "n":            {"type": "integer", "description": "Number of commits to return (default 10)"},
        },
        "required": ["project_slug", "repo"],
    },
    handler = _git_log,
)


# ---------------------------------------------------------------------------
# git_clone
# ---------------------------------------------------------------------------

async def _git_clone(args: dict) -> str:
    slug  = args["project_slug"]
    url   = args["url"]
    name  = args.get("name") or url.rstrip("/").split("/")[-1].removesuffix(".git")
    dest  = _PROJECTS_DIR / slug / "repos" / name
    cfg   = load_project_config(slug)
    mod   = cfg.get("git", {})
    token = mod.get("token", "")
    try:
        from modules.git.git_ops import clone_repo
        ok, msg = clone_repo(url, dest, token)
        if ok:
            repos = list(mod.get("repos", []))
            repos.append({"name": name, "url": url, "path": f"repos/{name}"})
            mod["repos"] = repos
            cfg["git"]   = mod
            save_project_config(slug, cfg)
        return json.dumps({"success": ok, "message": msg, "name": name})
    except Exception as exc:
        log.exception("git_clone skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "git",
    name        = "git_clone",
    description = "Clone a repository by URL into the project and register it.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "url":          {"type": "string", "description": "Repository clone URL (SSH or HTTPS)"},
            "name":         {"type": "string", "description": "Local directory name (optional, derived from URL)"},
        },
        "required": ["project_slug", "url"],
    },
    handler = _git_clone,
)
