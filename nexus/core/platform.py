from __future__ import annotations
import os
import shutil
import subprocess
import sys
from pathlib import Path


def open_path(path: str | Path) -> list[str]:
    """Return the command list to open a file or URL with the system default handler."""
    if sys.platform == "darwin":
        return ["open", str(path)]
    if sys.platform.startswith("win"):
        return ["start", str(path)]
    return ["xdg-open", str(path)]


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
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", f"Set-Clipboard -Value '{text}'"],
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
