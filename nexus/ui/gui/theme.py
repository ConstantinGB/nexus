from __future__ import annotations

# Default theme color constants (nexus-gui-legacy) — used by tile_grid and other
# widgets that reference individual colors directly.
BG        = "#1A0A2E"
SURFACE   = "#2D1B4E"
SURFACE2  = "#3A2260"
ACCENT_G  = "#00FF88"
ACCENT_B  = "#00D9FF"
ACCENT_P  = "#B45AFF"
ACCENT_M  = "#FF006E"
TEXT      = "#E0D0FF"
TEXT_DIM  = "#8070A0"

_INPUT_BG = "#0F0A1E"   # slightly darker than BG for inputs


def _make_theme(
    bg: str,
    surface: str,
    surface2: str,
    accent: str,     # primary highlight (border, selected tab, button text)
    accent2: str,    # secondary highlight (toolbar buttons, success)
    accent_p: str,   # purple-ish accent (scrollbar handle, focus border, headers)
    accent_m: str,   # magenta/hot accent (hover states)
    text: str,
    text_dim: str,
    input_bg: str,
) -> str:
    return f"""
QMainWindow, QDialog, QWidget {{
    background-color: {bg};
    color: {text};
    font-family: 'Fira Code', 'Consolas', 'Courier New', monospace;
    font-size: 13px;
}}
QScrollArea, QScrollArea > QWidget > QWidget {{
    background-color: {bg};
    border: none;
}}
QScrollBar:vertical {{
    background: {surface};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {accent_p};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QToolBar {{
    background: {surface};
    border-bottom: 1px solid {surface2};
    spacing: 6px;
    padding: 4px 8px;
}}
QToolButton {{
    background: transparent;
    color: {accent2};
    border: none;
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 13px;
}}
QToolButton:hover {{
    background: {surface2};
    color: {accent_m};
}}
QPushButton {{
    background-color: {surface};
    color: {accent2};
    border: 1px solid {accent_p};
    padding: 5px 14px;
    border-radius: 4px;
    min-width: 60px;
}}
QPushButton:hover {{
    border-color: {accent_m};
    color: {accent_m};
}}
QPushButton:pressed {{
    background-color: {surface2};
}}
QPushButton:disabled {{
    color: {text_dim};
    border-color: {surface2};
}}
QPushButton#primary {{
    background-color: {bg};
    border-color: {accent};
    color: {accent};
}}
QPushButton#primary:hover {{
    border-color: {accent2};
    color: {accent2};
}}
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {input_bg};
    color: {accent};
    border: 1px solid {surface2};
    border-radius: 4px;
    padding: 4px 8px;
    selection-background-color: {accent_p};
    selection-color: {bg};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {accent_p};
}}
QLabel {{
    color: {text};
    background: transparent;
}}
QLabel#title {{
    color: {accent2};
    font-size: 15px;
    font-weight: bold;
}}
QLabel#subtitle {{
    color: {accent_p};
    font-size: 12px;
}}
QLabel#dim {{
    color: {text_dim};
    font-size: 11px;
}}
QTabWidget::pane {{
    border: 1px solid {surface2};
    background: {bg};
}}
QTabBar::tab {{
    background: {surface};
    color: {text_dim};
    padding: 6px 16px;
    border: none;
    border-right: 1px solid {bg};
}}
QTabBar::tab:selected {{
    background: {bg};
    color: {accent2};
    border-bottom: 2px solid {accent2};
}}
QTabBar::tab:hover:!selected {{
    color: {accent_p};
}}
QTreeWidget, QListWidget, QTableWidget {{
    background-color: {input_bg};
    color: {text};
    border: 1px solid {surface2};
    border-radius: 4px;
    outline: none;
}}
QTreeWidget::item, QListWidget::item, QTableWidget::item {{
    padding: 4px 6px;
    border-bottom: 1px solid {surface};
}}
QTreeWidget::item:selected, QListWidget::item:selected, QTableWidget::item:selected {{
    background-color: {surface2};
    color: {accent2};
}}
QTreeWidget::item:hover, QListWidget::item:hover, QTableWidget::item:hover {{
    background-color: {surface};
}}
QHeaderView::section {{
    background-color: {surface};
    color: {accent_p};
    border: none;
    border-right: 1px solid {surface2};
    padding: 4px 8px;
    font-weight: bold;
}}
QComboBox {{
    background-color: {surface};
    color: {text};
    border: 1px solid {surface2};
    border-radius: 4px;
    padding: 4px 8px;
    min-width: 120px;
}}
QComboBox:hover {{ border-color: {accent_p}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background-color: {surface};
    color: {text};
    selection-background-color: {surface2};
    border: 1px solid {accent_p};
}}
QSplitter::handle {{
    background: {surface2};
    width: 2px;
    height: 2px;
}}
QStatusBar {{
    background: {surface};
    color: {text_dim};
    border-top: 1px solid {surface2};
}}
QMenuBar {{
    background: {surface};
    color: {text};
}}
QMenuBar::item:selected {{ background: {surface2}; color: {accent2}; }}
QMenu {{
    background: {surface};
    color: {text};
    border: 1px solid {accent_p};
}}
QMenu::item:selected {{ background: {surface2}; color: {accent2}; }}
QInputDialog QLabel {{ color: {text}; }}
QMessageBox QLabel {{ color: {text}; }}
"""


# All 7 GUI themes — names match TUI themes for user consistency.
GUI_THEMES: dict[str, str] = {
    "nexus-gui-legacy": _make_theme(
        bg="#1A0A2E", surface="#2D1B4E", surface2="#3A2260",
        accent="#00B4FF", accent2="#00FF88",
        accent_p="#B45AFF", accent_m="#FF006E",
        text="#E0D0FF", text_dim="#8070A0", input_bg="#0F0A1E",
    ),
    "vaporwave-red": _make_theme(
        bg="#1A0A0A", surface="#2D1B1B", surface2="#3A1515",
        accent="#CC2222", accent2="#FF8888",
        accent_p="#FF3333", accent_m="#FF6666",
        text="#FFE0E0", text_dim="#AA6060", input_bg="#100808",
    ),
    "vaporwave-blue": _make_theme(
        bg="#0A0F1A", surface="#1B254E", surface2="#1B2848",
        accent="#00CCFF", accent2="#88EEFF",
        accent_p="#00AADD", accent_m="#00FFFF",
        text="#E0F0FF", text_dim="#6090AA", input_bg="#070C14",
    ),
    "vaporwave-green": _make_theme(
        bg="#0A1A0E", surface="#1B3022", surface2="#152818",
        accent="#00DD44", accent2="#88FF88",
        accent_p="#00AA33", accent_m="#00FF66",
        text="#E0FFE8", text_dim="#60AA74", input_bg="#071209",
    ),
    "midnight-amber": _make_theme(
        bg="#0E0C18", surface="#1E1A2E", surface2="#2E2010",
        accent="#FFB300", accent2="#FFDD88",
        accent_p="#CC8800", accent_m="#FFC933",
        text="#FFF4E0", text_dim="#AA9060", input_bg="#0A0810",
    ),
    "neon-pink": _make_theme(
        bg="#1A0A1E", surface="#2D1B3E", surface2="#331530",
        accent="#FF006E", accent2="#FF66BB",
        accent_p="#CC0055", accent_m="#FF44AA",
        text="#FFE0FF", text_dim="#AA60AA", input_bg="#110814",
    ),
    "terminal-mono": _make_theme(
        bg="#0A0A0A", surface="#141414", surface2="#1A1A1A",
        accent="#33FF33", accent2="#99FF99",
        accent_p="#22AA22", accent_m="#66FF66",
        text="#CCFFCC", text_dim="#669966", input_bg="#050505",
    ),
}

GUI_THEME_LABELS: dict[str, str] = {
    "nexus-gui-legacy": "Nexus GUI Legacy",
    "vaporwave-red":    "Vaporwave Red",
    "vaporwave-blue":   "Vaporwave Blue",
    "vaporwave-green":  "Vaporwave Green",
    "midnight-amber":   "Midnight Amber",
    "neon-pink":        "Neon Pink",
    "terminal-mono":    "Terminal Mono",
}

DEFAULT_GUI_THEME = "nexus-gui-legacy"


def get_gui_theme(name: str) -> str:
    """Return the QSS stylesheet for the named GUI theme, falling back to legacy."""
    return GUI_THEMES.get(name, GUI_THEMES[DEFAULT_GUI_THEME])


# Keep RETROWAVE_THEME as an alias for the legacy theme for backwards compatibility.
RETROWAVE_THEME = GUI_THEMES["nexus-gui-legacy"]
