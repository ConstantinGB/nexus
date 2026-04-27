from __future__ import annotations
import asyncio
from datetime import date
from pathlib import Path

from textual.widgets import Label, Button, Log
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.core.platform import open_path
from nexus.ui.base_project_screen import BaseProjectScreen, _screen_css
from nexus.ui.text_editor_screen import TextEditorScreen

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
         "placeholder": "~/journal", "type": "dir"},
        {"id": "author", "label": "Author name (for LaTeX)",
         "placeholder": "Jane Doe"},
        {"id": "format",      "label": "Entry format (latex / markdown)",
         "placeholder": "latex"},
    ]

    DEFAULT_CSS = _screen_css("JournalProjectScreen")

    # ── Before-save hook ──────────────────────────────────────────────────────

    def _on_before_save(self, data: dict) -> dict:
        journal_dir = Path(data.get("journal_dir", "")).expanduser()
        if journal_dir and not journal_dir.exists():
            journal_dir.mkdir(parents=True, exist_ok=True)
            self.app.notify(f"Created: {journal_dir}", severity="information")
        return {}

    # ── Action buttons ────────────────────────────────────────────────────────

    def _compose_action_buttons(self) -> list:
        return [
            Button("New Entry",      id="btn-new-entry",     variant="primary"),
            Button("Compile Latest", id="btn-compile-latest"),
            Button("Open PDF",       id="btn-open-pdf"),
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
            entries = await asyncio.to_thread(lambda: sorted(
                entries_dir.rglob("*.tex"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            ))
            widgets.append(
                Horizontal(
                    Label("Entries:", classes="info-key"),
                    Label(str(len(entries)), classes="info-val"),
                    classes="info-row",
                )
            )
            widgets.append(Label("Recent entries:", classes="section-label"))
            for entry in entries[:15]:
                try:
                    wc = len((await asyncio.to_thread(entry.read_text, errors="replace")).split())
                except Exception:
                    wc = 0
                widgets.append(Label(f"  {entry.name}  ({wc:,} words)", classes="hint"))
        else:
            widgets.append(Label("No entries yet. Click 'New Entry' to start.", classes="hint"))

        await area.mount(*widgets)

    def _primary_folder(self) -> Path | None:
        p = Path(self._mod.get("journal_dir", "")).expanduser()
        return p if str(p) != "." else None

    # ── Button handler ────────────────────────────────────────────────────────

    def _handle_action(self, bid: str | None) -> None:
        journal_dir = Path(self._mod.get("journal_dir", "")).expanduser()
        author      = self._mod.get("author", "Author")

        if bid == "btn-new-entry":
            self._create_entry(journal_dir, author)
        elif bid == "btn-compile-latest":
            self._compile_latest(journal_dir)
        elif bid == "btn-open-pdf":
            pdfs = sorted(journal_dir.rglob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
            if pdfs:
                self.run_worker(self._run_cmd(open_path(pdfs[0])))
            else:
                self.app.notify("No PDF found — compile first.", severity="warning")
        elif bid == "btn-open-dir":
            self.run_worker(self._run_cmd(open_path(journal_dir)))

    def _create_entry(self, journal_dir: Path, author: str) -> None:
        today      = date.today()
        year_dir   = journal_dir / "entries" / str(today.year)
        entry_path = year_dir / f"{today}.tex"
        try:
            year_dir.mkdir(parents=True, exist_ok=True)
            if not entry_path.exists():
                entry_path.write_text(_LATEX_TEMPLATE.format(entry_date=today, author=author))
            content = entry_path.read_text(errors="replace")
        except Exception:
            log.exception("Failed to create journal entry: %s", entry_path)
            self.app.notify("Could not create entry — see log.", severity="error")
            return

        fmt  = self._mod.get("format", "latex")
        lang = "markdown" if fmt == "markdown" else "text"
        rel  = entry_path.relative_to(journal_dir)
        self.app.push_screen(
            TextEditorScreen(content, language=lang, title=str(rel)),
            lambda saved, p=entry_path: self._save_entry(p, saved),
        )

    def _save_entry(self, entry_path: Path, content: str | None) -> None:
        if content is None:
            return
        try:
            entry_path.write_text(content)
            self.app.notify(f"Saved: {entry_path.name}", severity="information")
        except Exception:
            log.exception("Failed to save journal entry: %s", entry_path)
            self.app.notify("Could not save entry — see log.", severity="error")
        self.run_worker(self._populate_content())

    def _compile_latest(self, journal_dir: Path) -> None:
        entries_dir = journal_dir / "entries"
        if not entries_dir.exists():
            self.app.notify("No entries directory found.", severity="warning")
            return
        entries = sorted(entries_dir.rglob("*.tex"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not entries:
            self.app.notify("No .tex entries found.", severity="warning")
            return
        self.run_worker(self._do_compile(entries[0], journal_dir))

    async def _do_compile(self, latest: Path, journal_dir: Path) -> None:
        ui_log = self.query_one("#output-log", Log)
        ui_log.write_line(f"$ pdflatex -interaction=nonstopmode {latest.name}")
        try:
            proc = await asyncio.create_subprocess_exec(
                "pdflatex", "-interaction=nonstopmode", str(latest),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(journal_dir),
            )
            if proc.stdout is None:
                log.error("subprocess stdout is None — cannot stream output")
                return
            error_lines: list[str] = []
            async for raw in proc.stdout:
                line = raw.decode(errors="replace").rstrip()
                ui_log.write_line(line)
                if line.startswith("!"):
                    error_lines.append(line)
            await proc.wait()
        except FileNotFoundError:
            ui_log.write_line("✗ pdflatex not found — install a TeX distribution.")
            self.app.notify("pdflatex not found.", severity="error")
            return
        except Exception:
            log.exception("pdflatex failed")
            ui_log.write_line("✗ Unexpected error — see log.")
            return

        if error_lines:
            ui_log.write_line(f"\n⚠ {len(error_lines)} LaTeX error(s):")
            for e in error_lines[:5]:
                ui_log.write_line(f"  {e}")
            self.app.notify(f"Compile finished with {len(error_lines)} error(s).", severity="warning")
        else:
            ui_log.write_line(f"\n✓ Compiled: {latest.stem}.pdf")
            self.app.notify("Compile complete.", severity="information")
