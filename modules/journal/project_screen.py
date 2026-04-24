from __future__ import annotations
from datetime import date
from pathlib import Path

from textual.widgets import Label, Button, Log
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.ui.base_project_screen import BaseProjectScreen, _screen_css

log = get("journal.project_screen")

_LATEX_TEMPLATE = r"""\documentclass[12pt,a4paper]{{article}}
\usepackage[utf8]{{inputenc}}
\usepackage[T1]{{fontenc}}
\usepackage{{geometry}}
\usepackage{{microtype}}
\geometry{{margin=2.5cm}}

\title{{Journal — {entry_date}}}
\author{{{author}}}
\date{{{entry_date}}}

\begin{{document}}
\maketitle

\section{{Entry}}

% Write your entry here.

\end{{document}}
"""


class JournalProjectScreen(BaseProjectScreen):
    MODULE_KEY   = "journal"
    MODULE_LABEL = "JOURNAL"
    SETUP_FIELDS = [
        {"id": "journal_dir", "label": "Journal directory",
         "placeholder": "~/journal"},
        {"id": "author", "label": "Author name (for LaTeX)",
         "placeholder": "Jane Doe"},
    ]

    DEFAULT_CSS = _screen_css("JournalProjectScreen")

    # ── Action buttons ────────────────────────────────────────────────────────

    def _compose_action_buttons(self) -> list:
        return [
            Button("New Entry",      id="btn-new-entry",     variant="primary"),
            Button("Compile Latest", id="btn-compile-latest"),
            Button("Open Dir",       id="btn-open-dir"),
        ]

    # ── Main content ──────────────────────────────────────────────────────────

    async def _populate_content(self) -> None:
        area = self.query_one("#content-area", Vertical)
        await area.remove_children()

        journal_dir = Path(self._mod.get("journal_dir", "")).expanduser()
        author      = self._mod.get("author", "")
        entries_dir = journal_dir / "entries"

        widgets: list = [
            Horizontal(
                Label("Journal dir:", classes="info-key"),
                Label(str(journal_dir), classes="info-val"),
                classes="info-row",
            ),
            Horizontal(
                Label("Author:", classes="info-key"),
                Label(author, classes="info-val"),
                classes="info-row",
            ),
        ]

        if entries_dir.exists():
            entries = sorted(
                entries_dir.rglob("*.tex"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            widgets.append(
                Horizontal(
                    Label("Entries:", classes="info-key"),
                    Label(str(len(entries)), classes="info-val"),
                    classes="info-row",
                )
            )
            widgets.append(Label("Recent entries:", classes="section-label"))
            for entry in entries[:15]:
                widgets.append(Label(f"  {entry.name}", classes="hint"))
        else:
            widgets.append(Label("No entries yet. Click 'New Entry' to start.", classes="hint"))

        await area.mount(*widgets)

    # ── Button handler ────────────────────────────────────────────────────────

    def _handle_action(self, bid: str | None) -> None:
        journal_dir = Path(self._mod.get("journal_dir", "")).expanduser()
        author      = self._mod.get("author", "Author")

        if bid == "btn-new-entry":
            self._create_entry(journal_dir, author)
        elif bid == "btn-compile-latest":
            self._compile_latest(journal_dir)
        elif bid == "btn-open-dir":
            self.run_worker(self._run_cmd(["xdg-open", str(journal_dir)]))

    def _create_entry(self, journal_dir: Path, author: str) -> None:
        today        = date.today()
        year_dir     = journal_dir / "entries" / str(today.year)
        entry_path   = year_dir / f"{today}.tex"
        try:
            year_dir.mkdir(parents=True, exist_ok=True)
            if not entry_path.exists():
                content = _LATEX_TEMPLATE.format(entry_date=today, author=author)
                entry_path.write_text(content)
            self.app.notify(f"Entry: {entry_path.relative_to(journal_dir)}")
            self.run_worker(self._populate_content())
        except Exception:
            log.exception("Failed to create journal entry: %s", entry_path)
            self.app.notify("Could not create entry — see log.", severity="error")

    def _compile_latest(self, journal_dir: Path) -> None:
        entries_dir = journal_dir / "entries"
        if not entries_dir.exists():
            self.app.notify("No entries directory found.", severity="warning")
            return
        entries = sorted(entries_dir.rglob("*.tex"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not entries:
            self.app.notify("No .tex entries found.", severity="warning")
            return
        latest = entries[0]
        self.run_worker(
            self._run_cmd(
                ["pdflatex", "-interaction=nonstopmode", str(latest)],
                cwd=str(journal_dir),
            )
        )
