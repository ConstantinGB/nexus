#!/bin/sh
# nexus-install.sh — Bootstrap script to install Nexus and its core dependencies.
#
# Usage:
#   ./nexus-install.sh                 (interactive menu)
#   ./nexus-install.sh --direct        (install from internet)
#   ./nexus-install.sh --local         (install from ./offline-packages/)
#   ./nexus-install.sh --download-only (download to ./offline-packages/ only)
#
# Supports: apt (Debian/Ubuntu), dnf (Fedora/RHEL), pacman (Arch)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OFFLINE_DIR="$SCRIPT_DIR/offline-packages"

# ── Colour helpers ─────────────────────────────────────────────────────────────

_green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
_yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
_red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
_bold()   { printf '\033[1m%s\033[0m\n'   "$*"; }

# ── Distro detection ───────────────────────────────────────────────────────────

detect_pm() {
    if command -v apt-get >/dev/null 2>&1; then
        echo "apt"
    elif command -v dnf >/dev/null 2>&1; then
        echo "dnf"
    elif command -v pacman >/dev/null 2>&1; then
        echo "pacman"
    else
        echo "unknown"
    fi
}

PM="$(detect_pm)"

# ── Package install helpers ────────────────────────────────────────────────────

pkg_install() {
    # pkg_install <pkg...>
    case "$PM" in
        apt)     sudo apt-get install -y "$@" ;;
        dnf)     sudo dnf install -y "$@" ;;
        pacman)  sudo pacman -S --noconfirm "$@" ;;
        *)       _red "Unknown package manager. Install manually: $*"; return 1 ;;
    esac
}

pkg_download() {
    # Download packages without installing
    mkdir -p "$OFFLINE_DIR"
    case "$PM" in
        apt)     sudo apt-get install -y --download-only -o Dir::Cache="$OFFLINE_DIR" "$@" ;;
        dnf)     sudo dnf download --destdir="$OFFLINE_DIR" "$@" ;;
        pacman)  sudo pacman -Sw --noconfirm --cachedir "$OFFLINE_DIR" "$@" ;;
        *)       _red "Unknown package manager."; return 1 ;;
    esac
}

pkg_install_local() {
    # Install from local cache
    case "$PM" in
        apt)
            sudo apt-get install -y --no-download \
                -o Dir::Cache="$OFFLINE_DIR" \
                -o APT::Get::AllowUnauthenticated=true "$@" 2>/dev/null \
            || sudo dpkg -i "$OFFLINE_DIR/archives/"*.deb 2>/dev/null || true
            ;;
        dnf)
            sudo dnf install -y "$OFFLINE_DIR"/*.rpm 2>/dev/null || true ;;
        pacman)
            sudo pacman -U --noconfirm "$OFFLINE_DIR"/*.pkg.tar.* 2>/dev/null || true ;;
        *)  _red "Unknown package manager."; return 1 ;;
    esac
}

# ── Core Python packages required by apt/dnf/pacman ───────────────────────────

_PYTHON_PKG_apt="python3.12 python3.12-venv"
_PYTHON_PKG_dnf="python3.12"
_PYTHON_PKG_pacman="python"

python_pkg() {
    eval echo "\$_PYTHON_PKG_${PM}"
}

# ── Install uv ────────────────────────────────────────────────────────────────

install_uv() {
    if command -v uv >/dev/null 2>&1; then
        _green "uv already installed: $(uv --version)"
        return
    fi
    _yellow "Installing uv…"
    if [ "$MODE" = "local" ]; then
        if [ -f "$OFFLINE_DIR/uv-installer.sh" ]; then
            sh "$OFFLINE_DIR/uv-installer.sh"
        else
            _red "uv installer not found in $OFFLINE_DIR. Run --download-only first."
            exit 1
        fi
    elif [ "$MODE" = "download" ]; then
        curl -Ls https://astral.sh/uv/install.sh -o "$OFFLINE_DIR/uv-installer.sh"
        _green "uv installer saved to $OFFLINE_DIR/uv-installer.sh"
    else
        curl -Ls https://astral.sh/uv/install.sh | sh
    fi
}

# ── Install Python ────────────────────────────────────────────────────────────

install_python() {
    if command -v python3.12 >/dev/null 2>&1 || command -v python3 >/dev/null 2>&1; then
        PY="$(command -v python3.12 || command -v python3)"
        VER="$($PY --version 2>&1)"
        _green "Python found: $VER"
        return
    fi
    _yellow "Installing Python 3.12…"
    PKG="$(python_pkg)"
    if [ "$MODE" = "local" ]; then
        pkg_install_local $PKG
    elif [ "$MODE" = "download" ]; then
        pkg_download $PKG
    else
        pkg_install $PKG
    fi
}

# ── Set up directory structure ────────────────────────────────────────────────

setup_dirs() {
    _yellow "Creating required directories…"
    mkdir -p "$SCRIPT_DIR/config"
    mkdir -p "$SCRIPT_DIR/projects"
    mkdir -p "$SCRIPT_DIR/logs"
    if [ ! -f "$SCRIPT_DIR/config/settings.yaml" ]; then
        if [ -f "$SCRIPT_DIR/config/settings.example.yaml" ]; then
            cp "$SCRIPT_DIR/config/settings.example.yaml" \
               "$SCRIPT_DIR/config/settings.yaml"
            _green "Created config/settings.yaml from example."
        fi
    else
        _green "config/settings.yaml already exists."
    fi
}

# ── uv sync ───────────────────────────────────────────────────────────────────

run_uv_sync() {
    if [ "$MODE" = "download" ]; then
        _yellow "Downloading Python dependencies…"
        uv sync --no-install-project 2>/dev/null \
            || uv pip compile pyproject.toml -o "$OFFLINE_DIR/requirements.txt" 2>/dev/null \
            || true
        _green "Dependencies cached. Transfer offline-packages/ with the project."
        return
    fi
    _yellow "Installing Python dependencies via uv sync…"
    cd "$SCRIPT_DIR"
    uv sync
}

# ── Mode: download-only ───────────────────────────────────────────────────────

do_download_only() {
    _bold "Mode: Download Only"
    _yellow "Downloading all packages to $OFFLINE_DIR …"
    mkdir -p "$OFFLINE_DIR"
    PKG="$(python_pkg)"
    pkg_download $PKG
    curl -Ls https://astral.sh/uv/install.sh -o "$OFFLINE_DIR/uv-installer.sh"
    run_uv_sync
    _green "Done. Transfer nexus/ (including offline-packages/) to the target machine."
    _green "Then run: ./nexus-install.sh --local"
}

# ── Mode: local install ───────────────────────────────────────────────────────

do_local() {
    _bold "Mode: Local Install (from $OFFLINE_DIR)"
    if [ ! -d "$OFFLINE_DIR" ]; then
        _red "offline-packages/ not found. Run --download-only first."
        exit 1
    fi
    install_python
    install_uv
    run_uv_sync
    setup_dirs
    _green ""
    _green "Nexus installed from local packages."
    _green "Run: uv run nexus"
}

# ── Mode: direct install ──────────────────────────────────────────────────────

do_direct() {
    _bold "Mode: Install Direct (from internet)"
    install_python
    install_uv
    run_uv_sync
    setup_dirs
    _green ""
    _green "Nexus installed."
    _green "Run: uv run nexus"
    _green ""
    _green "Tip: Press 's' in Nexus to open Settings → Setup to install"
    _green "     software for individual modules (git, OBS, restic, etc.)."
}

# ── Interactive menu ──────────────────────────────────────────────────────────

interactive_menu() {
    _bold "Nexus Install"
    echo ""
    echo "  1) Install Direct      — download and install from the internet"
    echo "  2) Download + Install  — download to offline-packages/, then install"
    echo "  3) Download Only       — download to offline-packages/ (for portable use)"
    echo ""
    printf "Choose [1/2/3]: "
    read -r choice
    case "$choice" in
        1) MODE="direct";   do_direct ;;
        2) MODE="local";    pkg_download "$(python_pkg)" 2>/dev/null; MODE="local"; do_local ;;
        3) MODE="download"; do_download_only ;;
        *) _red "Invalid choice."; exit 1 ;;
    esac
}

# ── Entry point ───────────────────────────────────────────────────────────────

case "${1:-}" in
    --direct)        MODE="direct";   do_direct ;;
    --local)         MODE="local";    do_local ;;
    --download-only) MODE="download"; do_download_only ;;
    --help|-h)
        echo "Usage: $0 [--direct | --local | --download-only | --help]"
        echo ""
        echo "  --direct        Install from internet (default interactive option 1)"
        echo "  --local         Install from ./offline-packages/"
        echo "  --download-only Download packages only (for offline/portable use)"
        exit 0
        ;;
    "")
        interactive_menu ;;
    *)
        _red "Unknown option: $1"
        echo "Run '$0 --help' for usage."
        exit 1
        ;;
esac
