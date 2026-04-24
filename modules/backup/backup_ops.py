from __future__ import annotations
import os
import subprocess


def _env(password: str) -> dict[str, str]:
    e = os.environ.copy()
    e["RESTIC_PASSWORD"] = password
    return e


def _p(path: str) -> str:
    """Expand ~ and resolve to an absolute path."""
    return os.path.abspath(os.path.expanduser(path))


def _already_initialized(out: str) -> bool:
    return "already initialized" in out.lower() or "config file already exists" in out.lower()


def restic_ensure_initialized(repo: str, password: str) -> tuple[bool, str]:
    """
    Init the repo if not already done. Returns (True, msg) if the repo is
    ready to use (either freshly initialized or already was). Creates the
    directory for local repos if it doesn't exist.
    """
    repo = _p(repo)
    if not repo.startswith("sftp:") and not repo.startswith("s3:"):
        os.makedirs(repo, exist_ok=True)
    try:
        r = subprocess.run(
            ["restic", "-r", repo, "init"],
            capture_output=True, text=True, env=_env(password),
        )
        out = (r.stdout + r.stderr).strip()
        if r.returncode == 0:
            return True, "Repository initialised."
        if _already_initialized(out):
            return True, "Repository already initialised."
        return False, out
    except FileNotFoundError:
        return False, "restic not found — install it first (Settings → Setup)."
    except Exception as exc:
        return False, str(exc)


def restic_init(repo: str, password: str) -> tuple[bool, str]:
    repo = _p(repo)
    try:
        r = subprocess.run(
            ["restic", "-r", repo, "init"],
            capture_output=True, text=True, env=_env(password),
        )
        out = (r.stdout + r.stderr).strip()
        return r.returncode == 0, out
    except FileNotFoundError:
        return False, "restic not found — install it first (Settings → Setup)."
    except Exception as exc:
        return False, str(exc)


def restic_backup(repo: str, password: str, paths: list[str]) -> tuple[bool, str]:
    repo  = _p(repo)
    paths = [_p(p) for p in paths]
    try:
        r = subprocess.run(
            ["restic", "-r", repo, "backup"] + paths,
            capture_output=True, text=True, env=_env(password),
        )
        out = (r.stdout + r.stderr).strip()
        return r.returncode == 0, out
    except FileNotFoundError:
        return False, "restic not found."
    except Exception as exc:
        return False, str(exc)


def restic_snapshots(repo: str, password: str) -> tuple[bool, str]:
    repo = _p(repo)
    try:
        r = subprocess.run(
            ["restic", "-r", repo, "snapshots", "--compact"],
            capture_output=True, text=True, env=_env(password),
        )
        out = (r.stdout + r.stderr).strip()
        return r.returncode == 0, out
    except FileNotFoundError:
        return False, "restic not found."
    except Exception as exc:
        return False, str(exc)


def restic_restore(repo: str, password: str,
                   snapshot_id: str, target: str) -> tuple[bool, str]:
    repo   = _p(repo)
    target = _p(target)
    try:
        r = subprocess.run(
            ["restic", "-r", repo, "restore", snapshot_id, "--target", target],
            capture_output=True, text=True, env=_env(password),
        )
        out = (r.stdout + r.stderr).strip()
        return r.returncode == 0, out
    except FileNotFoundError:
        return False, "restic not found."
    except Exception as exc:
        return False, str(exc)


def restic_check(repo: str, password: str) -> tuple[bool, str]:
    repo = _p(repo)
    try:
        r = subprocess.run(
            ["restic", "-r", repo, "check"],
            capture_output=True, text=True, env=_env(password),
        )
        out = (r.stdout + r.stderr).strip()
        return r.returncode == 0, out
    except FileNotFoundError:
        return False, "restic not found."
    except Exception as exc:
        return False, str(exc)


def restic_forget(repo: str, password: str,
                  keep_daily: int = 7, keep_weekly: int = 4) -> tuple[bool, str]:
    repo = _p(repo)
    try:
        r = subprocess.run(
            [
                "restic", "-r", repo, "forget",
                "--keep-daily",  str(keep_daily),
                "--keep-weekly", str(keep_weekly),
                "--prune",
            ],
            capture_output=True, text=True, env=_env(password),
        )
        out = (r.stdout + r.stderr).strip()
        return r.returncode == 0, out
    except FileNotFoundError:
        return False, "restic not found."
    except Exception as exc:
        return False, str(exc)
