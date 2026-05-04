from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name:       str
    label:      str
    bg:         str
    surface:    str
    border:     str
    accent:     str
    accent2:    str
    text:       str
    text_dim:   str
    border_dim: str   # inactive borders / separators


THEMES: dict[str, Theme] = {
    "nexus-legacy": Theme(
        "nexus-legacy", "Nexus Legacy",
        "#1A0A2E", "#2D1B4E", "#00B4FF", "#00B4FF", "#00FF88",
        "#E0E0FF", "#8080AA", "#3A2260",
    ),
    "vaporwave-red": Theme(
        "vaporwave-red", "Nexus Vaporwave Red",
        "#1A0A0A", "#2D1B1B", "#CC2222", "#FF3333", "#FF8888",
        "#FFE0E0", "#AA6060", "#3A1515",
    ),
    "vaporwave-blue": Theme(
        "vaporwave-blue", "Nexus Vaporwave Blue",
        "#0A0F1A", "#1B254E", "#00CCFF", "#00DDFF", "#88EEFF",
        "#E0F0FF", "#6090AA", "#1B2848",
    ),
    "vaporwave-green": Theme(
        "vaporwave-green", "Nexus Vaporwave Green",
        "#0A1A0E", "#1B3022", "#00DD44", "#00FF55", "#88FF88",
        "#E0FFE8", "#60AA74", "#152818",
    ),
    "midnight-amber": Theme(
        "midnight-amber", "Midnight Amber",
        "#0E0C18", "#1E1A2E", "#FFB300", "#FFB300", "#FFDD88",
        "#FFF4E0", "#AA9060", "#2E2010",
    ),
    "neon-pink": Theme(
        "neon-pink", "Neon Pink",
        "#1A0A1E", "#2D1B3E", "#FF006E", "#FF006E", "#FF66BB",
        "#FFE0FF", "#AA60AA", "#331530",
    ),
    "terminal-mono": Theme(
        "terminal-mono", "Terminal Mono",
        "#0A0A0A", "#141414", "#33FF33", "#33FF33", "#99FF99",
        "#CCFFCC", "#669966", "#1A1A1A",
    ),
}

DEFAULT_THEME = "nexus-legacy"


def get(name: str) -> Theme:
    return THEMES.get(name, THEMES[DEFAULT_THEME])
