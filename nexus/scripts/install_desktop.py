"""
Install a .desktop launcher for Nexus so it appears in the application menu
and can be pinned to the GNOME/KDE taskbar.

Run via:  uv run nexus install-desktop
Or:       python -m nexus.scripts.install_desktop
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent


def _nexus_executable() -> str:
    """Return the full path to the nexus entry-point in the active venv."""
    venv_bin = Path(sys.executable).parent
    nexus_bin = venv_bin / "nexus"
    if nexus_bin.exists():
        return str(nexus_bin)
    # Fallback: invoke via python -m
    return f"{sys.executable} -m nexus.app"


def _install_icon() -> Path:
    icon_src = _REPO_ROOT / "nexus" / "assets" / "icons" / "nexus.svg"
    icon_dir = Path.home() / ".local" / "share" / "icons" / "hicolor" / "scalable" / "apps"
    icon_dir.mkdir(parents=True, exist_ok=True)
    icon_dst = icon_dir / "nexus.svg"
    shutil.copy2(icon_src, icon_dst)
    return icon_dst


def _desktop_content(exec_path: str) -> str:
    return f"""\
[Desktop Entry]
Type=Application
Version=1.5
Name=Nexus
GenericName=Project Manager
Comment=Personal project manager with AI integration
Exec={exec_path} --gui
Icon=nexus
Terminal=false
Categories=Utility;Office;Development;
Keywords=nexus;project;ai;assistant;organiser;
StartupNotify=true
StartupWMClass=nexus
"""


def install() -> None:
    exec_path   = _nexus_executable()
    icon_dst    = _install_icon()

    apps_dir = Path.home() / ".local" / "share" / "applications"
    apps_dir.mkdir(parents=True, exist_ok=True)
    desktop_dst = apps_dir / "nexus.desktop"
    content = _desktop_content(exec_path)
    if not content.startswith("[Desktop Entry]"):
        raise RuntimeError("Desktop file content is malformed — aborting.")
    desktop_dst.write_text(content, encoding="utf-8")
    os.chmod(desktop_dst, 0o755)

    # Refresh desktop database so the launcher is discoverable immediately
    for cmd in (
        ["update-desktop-database", str(apps_dir)],
        ["gtk-update-icon-cache", "-f", "-t",
         str(Path.home() / ".local" / "share" / "icons" / "hicolor")],
    ):
        try:
            subprocess.run(cmd, check=False, capture_output=True)
        except FileNotFoundError:
            pass

    print(f"✓ Icon installed:   {icon_dst}")
    print(f"✓ Launcher written: {desktop_dst}")
    print(f"  Exec: {exec_path} --gui")
    print()
    print("Nexus is now in your application launcher.")
    print("Right-click the icon in the launcher to pin it to your taskbar/dock.")


if __name__ == "__main__":
    install()
