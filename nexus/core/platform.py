from __future__ import annotations
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("nexus.core.platform")


def is_wsl() -> bool:
    """True when running inside Windows Subsystem for Linux."""
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False

# Keep private alias so existing internal callers still work
_is_wsl = is_wsl


def is_wsl_1() -> bool:
    """True when running in WSL 1 (limited POSIX support — no full ioctl, no /proc/net)."""
    if not is_wsl():
        return False
    try:
        import re
        v = Path("/proc/version").read_text()
        m = re.search(r"Linux version (\d+)\.", v)
        return bool(m and int(m.group(1)) < 5)
    except OSError:
        return False


def open_path(path: str | Path) -> list[str]:
    """Return the best available command list to open a file, directory, or URL.

    Priority on Linux: xdg-open → wslview → explorer.exe (WSL) → nautilus/dolphin/thunar.
    Falls back to ["xdg-open", ...] even when not found so callers that stream output
    through _run_cmd() still display a useful error in the TUI log.
    """
    p = str(path)
    if sys.platform == "darwin":
        return ["open", p]
    if sys.platform.startswith("win"):
        return ["cmd", "/c", "start", "", p]
    # Linux — prefer xdg-open, then WSL helpers, then bare file managers
    if shutil.which("xdg-open"):
        return ["xdg-open", p]
    if _is_wsl():
        if shutil.which("wslview"):          # wslu package
            return ["wslview", p]
        if shutil.which("explorer.exe"):
            return ["explorer.exe", p]
    for fm in ("nautilus", "dolphin", "thunar", "nemo", "pcmanfm"):
        if shutil.which(fm):
            return [fm, p]
    return ["xdg-open", p]  # best error message when nothing is found


def launch(path: str | Path) -> None:
    """Open a file, directory, or URL with the system default handler (fire-and-forget).

    Use this from GUI code.  TUI code should use _run_cmd(open_path(path)) instead
    so errors are visible in the output log.
    """
    cmd = open_path(path)
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        log.warning("launch: opener not found: %r (path=%s)", cmd[0], path)
    except Exception as exc:
        log.warning("launch: failed to open %s: %s", path, exc)


def check_binary(name_or_path: str) -> bool:
    """Return True if the binary is executable — by PATH lookup or as an absolute path."""
    p = Path(name_or_path).expanduser()
    if p.is_absolute():
        return p.is_file() and os.access(p, os.X_OK)
    return shutil.which(name_or_path) is not None


def read_clipboard() -> str:
    """Read text from the system clipboard. Returns empty string on failure."""
    try:
        import pyperclip  # type: ignore
        return pyperclip.paste() or ""
    except Exception:
        pass
    if sys.platform == "darwin" and shutil.which("pbpaste"):
        try:
            return subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=2).stdout
        except Exception:
            pass
    if sys.platform.startswith("win"):
        try:
            return subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=2,
            ).stdout.rstrip("\r\n")
        except Exception:
            pass
    # Linux: try Wayland then X11
    if shutil.which("wl-paste"):
        try:
            r = subprocess.run(["wl-paste", "--no-newline"], capture_output=True, text=True, timeout=2)
            if r.returncode == 0:
                return r.stdout
        except Exception:
            pass
    if shutil.which("xclip"):
        try:
            r = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True, text=True, timeout=2,
            )
            if r.returncode == 0:
                return r.stdout
        except Exception:
            pass
    if shutil.which("xsel"):
        try:
            r = subprocess.run(["xsel", "--clipboard", "--output"], capture_output=True, text=True, timeout=2)
            if r.returncode == 0:
                return r.stdout
        except Exception:
            pass
    return ""


def write_clipboard(text: str) -> None:
    """Write text to the system clipboard. Silently ignores failures."""
    try:
        import pyperclip  # type: ignore
        pyperclip.copy(text)
        return
    except Exception:
        pass
    if sys.platform == "darwin" and shutil.which("pbcopy"):
        try:
            subprocess.run(["pbcopy"], input=text.encode(), timeout=2)
            return
        except Exception:
            pass
    if sys.platform.startswith("win"):
        try:
            # Pass text via env var — never interpolate user content into the command string
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Set-Clipboard -Value $env:_NEXUS_CB"],
                env={**os.environ, "_NEXUS_CB": text},
                timeout=2,
            )
            return
        except Exception:
            pass
    if shutil.which("wl-copy"):
        try:
            subprocess.run(["wl-copy"], input=text.encode(), timeout=2)
            return
        except Exception:
            pass
    if shutil.which("xclip"):
        try:
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), timeout=2)
            return
        except Exception:
            pass
    if shutil.which("xsel"):
        try:
            subprocess.run(["xsel", "--clipboard", "--input"], input=text.encode(), timeout=2)
        except Exception:
            pass
