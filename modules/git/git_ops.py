from __future__ import annotations
import shutil
import subprocess
from pathlib import Path

from nexus.core.logger import get

log = get("git.ops")


# ---------------------------------------------------------------------------
# Installation helpers
# ---------------------------------------------------------------------------

def git_installed() -> bool:
    result = shutil.which("git") is not None
    log.debug("git_installed -> %s", result)
    return result


def detect_package_manager() -> str | None:
    for pm in ("apt", "dnf", "pacman", "brew"):
        if shutil.which(pm):
            log.debug("Detected package manager: %s", pm)
            return pm
    log.warning("No supported package manager found")
    return None


def install_git_command(pm: str) -> list[str]:
    return {
        "apt":    ["sudo", "apt", "install", "-y", "git"],
        "dnf":    ["sudo", "dnf",  "install", "-y", "git"],
        "pacman": ["sudo", "pacman", "-S", "--noconfirm", "git"],
        "brew":   ["brew", "install", "git"],
    }[pm]


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------

def _git(repo_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True, text=True,
    )


def clone_repo(url: str, dest: Path, token: str = "") -> tuple[bool, str]:
    display_url = url  # keep original for logging (token injected separately)
    try:
        if token and url.startswith("https://"):
            url = url.replace("https://", f"https://oauth2:{token}@", 1)
        log.info("Cloning %s -> %s", display_url, dest)
        result = subprocess.run(
            ["git", "clone", url, str(dest)],
            capture_output=True, text=True,
        )
        msg = (result.stderr or result.stdout).strip()
        if result.returncode == 0:
            log.info("Clone OK: %s", dest.name)
        else:
            log.error("Clone failed for %s: %s", dest.name, msg)
        return result.returncode == 0, msg
    except Exception as exc:
        log.exception("Unexpected error cloning %s", display_url)
        return False, str(exc)


def pull_repo(repo_path: Path) -> tuple[bool, str]:
    try:
        log.info("Pulling %s", repo_path.name)
        r = _git(repo_path, "pull")
        msg = (r.stdout + r.stderr).strip()
        if r.returncode == 0:
            log.info("Pull OK: %s", repo_path.name)
        else:
            log.warning("Pull failed for %s: %s", repo_path.name, msg)
        return r.returncode == 0, msg
    except Exception as exc:
        log.exception("Unexpected error pulling %s", repo_path)
        return False, str(exc)


def push_repo(repo_path: Path) -> tuple[bool, str]:
    try:
        log.info("Pushing %s", repo_path.name)
        r = _git(repo_path, "push")
        msg = (r.stdout + r.stderr).strip()
        if r.returncode == 0:
            log.info("Push OK: %s", repo_path.name)
        else:
            log.warning("Push failed for %s: %s", repo_path.name, msg)
        return r.returncode == 0, msg
    except Exception as exc:
        log.exception("Unexpected error pushing %s", repo_path)
        return False, str(exc)


def commit_and_push(repo_path: Path, message: str) -> tuple[bool, str]:
    try:
        log.info("Commit+push %s — '%s'", repo_path.name, message[:60])
        for cmd in (["add", "-A"], ["commit", "-m", message]):
            r = _git(repo_path, *cmd)
            if r.returncode != 0:
                msg = (r.stdout + r.stderr).strip()
                log.warning("Commit step failed for %s: %s", repo_path.name, msg)
                return False, msg
        r = _git(repo_path, "push")
        msg = (r.stdout + r.stderr).strip()
        if r.returncode == 0:
            log.info("Commit+push OK: %s", repo_path.name)
        else:
            log.warning("Push step failed for %s: %s", repo_path.name, msg)
        return r.returncode == 0, msg
    except Exception as exc:
        log.exception("Unexpected error in commit_and_push for %s", repo_path)
        return False, str(exc)


def delete_repo(repo_path: Path) -> None:
    import shutil as _shutil
    try:
        log.info("Deleting repo at %s", repo_path)
        _shutil.rmtree(repo_path)
        log.info("Deleted %s", repo_path.name)
    except Exception as exc:
        log.exception("Failed to delete repo at %s", repo_path)
        raise


# ---------------------------------------------------------------------------
# Status / info
# ---------------------------------------------------------------------------

def get_repo_status(repo_path: Path) -> dict:
    if not (repo_path / ".git").exists():
        log.debug("get_repo_status: no .git at %s", repo_path)
        return {"branch": "?", "ahead": 0, "behind": 0, "dirty": False, "valid": False}
    try:
        branch = _git(repo_path, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        dirty  = bool(_git(repo_path, "status", "--porcelain").stdout.strip())
        ab     = _git(repo_path, "rev-list", "--count", "--left-right", "HEAD...@{upstream}")
        ahead  = behind = 0
        if ab.returncode == 0:
            parts = ab.stdout.strip().split()
            if len(parts) == 2:
                ahead, behind = int(parts[0]), int(parts[1])
        log.debug("Status %s: branch=%s ahead=%d behind=%d dirty=%s",
                  repo_path.name, branch, ahead, behind, dirty)
        return {"branch": branch, "ahead": ahead, "behind": behind,
                "dirty": dirty, "valid": True}
    except Exception as exc:
        log.exception("get_repo_status failed for %s", repo_path)
        return {"branch": "error", "ahead": 0, "behind": 0, "dirty": False, "valid": False}


def get_last_updated(repo_path: Path) -> str:
    try:
        r = _git(repo_path, "log", "-1", "--pretty=format:%ar")
        return r.stdout.strip() or "never"
    except Exception:
        log.exception("get_last_updated failed for %s", repo_path)
        return "unknown"


def get_branches(repo_path: Path) -> list[str]:
    try:
        r = _git(repo_path, "branch", "-a")
        return [l.strip().lstrip("* ") for l in r.stdout.splitlines() if l.strip()]
    except Exception:
        log.exception("get_branches failed for %s", repo_path)
        return []


def get_recent_commits(repo_path: Path, n: int = 10) -> list[dict]:
    try:
        r = _git(repo_path, "log", f"-{n}", "--pretty=format:%h|%s|%an|%ar")
        commits = []
        for line in r.stdout.splitlines():
            parts = line.split("|", 3)
            if len(parts) == 4:
                commits.append({"hash": parts[0], "message": parts[1],
                                "author": parts[2], "date": parts[3]})
        return commits
    except Exception:
        log.exception("get_recent_commits failed for %s", repo_path)
        return []


def fetch_remote(repo_path: Path) -> None:
    try:
        log.debug("Fetching remote for %s", repo_path.name)
        _git(repo_path, "fetch", "--quiet")
    except Exception:
        log.warning("fetch_remote failed for %s", repo_path, exc_info=True)


def checkout_branch(repo_path: Path, branch: str) -> tuple[bool, str]:
    try:
        log.info("Checkout branch %s in %s", branch, repo_path.name)
        r = _git(repo_path, "checkout", branch)
        msg = (r.stdout + r.stderr).strip()
        if r.returncode != 0:
            log.warning("Checkout failed: %s", msg)
        return r.returncode == 0, msg
    except Exception as exc:
        log.exception("checkout_branch failed for %s", repo_path)
        return False, str(exc)


def create_branch(repo_path: Path, name: str) -> tuple[bool, str]:
    try:
        log.info("Create+checkout branch %s in %s", name, repo_path.name)
        r = _git(repo_path, "checkout", "-b", name)
        msg = (r.stdout + r.stderr).strip()
        if r.returncode != 0:
            log.warning("Create branch failed: %s", msg)
        return r.returncode == 0, msg
    except Exception as exc:
        log.exception("create_branch failed for %s", repo_path)
        return False, str(exc)


def get_short_status(repo_path: Path) -> str:
    """Return `git status --short` output."""
    try:
        return _git(repo_path, "status", "--short").stdout.strip()
    except Exception:
        log.exception("get_short_status failed for %s", repo_path)
        return ""


def list_stashes(repo_path: Path) -> list[str]:
    try:
        r = _git(repo_path, "stash", "list")
        return [l.strip() for l in r.stdout.splitlines() if l.strip()]
    except Exception:
        log.exception("list_stashes failed for %s", repo_path)
        return []


def stash_push(repo_path: Path, message: str = "") -> tuple[bool, str]:
    try:
        cmd = ["stash", "push"] + (["-m", message] if message else [])
        log.info("Stash push in %s", repo_path.name)
        r = _git(repo_path, *cmd)
        msg = (r.stdout + r.stderr).strip()
        if r.returncode != 0:
            log.warning("Stash push failed: %s", msg)
        return r.returncode == 0, msg
    except Exception as exc:
        log.exception("stash_push failed for %s", repo_path)
        return False, str(exc)


def stash_pop(repo_path: Path) -> tuple[bool, str]:
    try:
        log.info("Stash pop in %s", repo_path.name)
        r = _git(repo_path, "stash", "pop")
        msg = (r.stdout + r.stderr).strip()
        if r.returncode != 0:
            log.warning("Stash pop failed: %s", msg)
        return r.returncode == 0, msg
    except Exception as exc:
        log.exception("stash_pop failed for %s", repo_path)
        return False, str(exc)


def scan_local_repos(base_path: Path) -> list[Path]:
    try:
        if not base_path.exists():
            log.warning("scan_local_repos: path does not exist: %s", base_path)
            return []
        found = [d for d in sorted(base_path.iterdir())
                 if d.is_dir() and (d / ".git").exists()]
        log.info("scan_local_repos found %d repos under %s", len(found), base_path)
        return found
    except Exception:
        log.exception("scan_local_repos failed for %s", base_path)
        return []
