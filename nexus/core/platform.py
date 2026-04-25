from __future__ import annotations
import os
import shutil
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
