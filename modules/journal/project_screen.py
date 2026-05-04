from __future__ import annotations
import asyncio
from datetime import date
from pathlib import Path

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, Button, Log, Checkbox
from textual.containers import Vertical, Horizontal, ScrollableContainer

from nexus.core.logger import get
from nexus.ui.tui.base_project_screen import BaseProjectScreen, ConfirmModal, _screen_css

log = get("journal.project_screen")

_LATEX_TEMPLATE = r"""\documentclass[12pt,{geometry}]{{article}}
\usepackage[utf8]{{inputenc}}
\usepackage[T1]{{fontenc}}
\usepackage{{geometry}}
\usepackage{{microtype}}
\geometry{{margin={margin}}}

\title{{Journal — {entry_date}}}
\author{{{author}}}
\date{{{entry_date}}}

\begin{{document}}
\maketitle

\section{{Entry}}

% Write your entry here.

\end{{document}}
"""

_LATEX_TEMPLATE_SIMPLE = r"""\documentclass[12pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{geometry}
\usepackage{microtype}
\geometry{margin=2.5cm}

\title{Journal --- %s}
\author{%s}
\date{%s}

\begin{document}
\maketitle

\section{Entry}

%% Write your entry here.

\end{document}
"""

_LATEX_SPECIAL = str.maketrans({
    "\\": r"\textbackslash{}",
    "{":  r"\{",
    "}":  r"\}",
    "$":  r"\$",
    "&":  r"\&",
    "%":  r"\%",
    "#":  r"\#",
    "_":  r"\_",
    "^":  r"\^{}",
    "~":  r"\textasciitilde{}",
})


def _latex_escape(text: str) -> str:
    return text.translate(_LATEX_SPECIAL)


class CompileSelectModal(ModalScreen[list | None]):
    DEFAULT_CSS = """
    CompileSelectModal { align: center middle; }
    #csm-box {
        background: #2D1B4E; border: solid #00B4FF;
        padding: 1 2; width: 70; height: auto; max-height: 40;
    }
    #csm-title { color: #00B4FF; text-style: bold; height: 2; }
    #csm-scroll { height: auto; max-height: 20; }
    .csm-entry-row { height: 3; }
    #csm-btns  { height: 3; margin-top: 1; }
    #csm-btns Button { margin-right: 1; }
    """

    def __init__(self, entries: list[Path]) -> None:
        super().__init__()
        self._entries = entries

    def compose(self) -> ComposeResult:
        with Vertical(id="csm-box"):
            yield Label("Select entries to compile:", id="csm-title")
            with ScrollableContainer(id="csm-scroll"):
                for i, entry in enumerate(self._entries):
                    yield Checkbox(entry.name, id=f"csm-entry-{i}", value=True,
                                   classes="csm-entry-row")
            with Horizontal(id="csm-btns"):
                yield Button("Compile", id="csm-compile", variant="primary")
                yield Button("Cancel",  id="csm-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "csm-compile":
            selected = []
            for i, entry in enumerate(self._entries):
                try:
                    if self.query_one(f"#csm-entry-{i}", Checkbox).value:
                        selected.append(entry)
                except Exception:
                    pass
            self.dismiss(selected if selected else None)
        else:
            self.dismiss(None)


class ProjectScreen(BaseProjectScreen):
    MODULE_KEY        = "journal"
    MODULE_LABEL      = "JOURNAL"
    REQUIRED_BINARIES = [("pdflatex", "pdflatex (texlive-latex-base)")]
    SETUP_FIELDS      = [
        {"id": "journal_dir", "label": "Journal directory",
         "placeholder": "~/journal", "type": "dir"},
        {"id": "author", "label": "Author name (for LaTeX)",
         "placeholder": "Jane Doe"},
        {"id": "format",      "label": "Entry format (latex / markdown)",
         "placeholder": "latex"},
    ]

    DEFAULT_CSS = _screen_css("JournalProjectScreen") + """
    .entry-item { width: 1fr; height: 2; border: none; background: transparent;
                  color: #8080AA; text-align: left; margin: 0; }
    .entry-item:hover { background: #2D1B4E; color: #E0E0FF; }
    .entry-del-btn { width: 4; height: 2; border: none; background: transparent;
                     color: #555588; min-width: 4; }
    .entry-del-btn:hover { color: #FF4444; background: transparent; }
    .entry-row { height: 2; }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._entries: list[Path] = []

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
            Button("New Entry", id="btn-new-entry", variant="primary"),
            Button("Compile",   id="btn-compile"),
            Button("Open PDF",  id="btn-open-pdf"),
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
            self._entries = entries[:30]
            widgets.append(
                Horizontal(
                    Label("Entries:", classes="info-key"),
                    Label(str(len(entries)), classes="info-val"),
                    classes="info-row",
                )
            )
            widgets.append(Label("Recent entries (click to edit):", classes="section-label"))
            for i, entry in enumerate(self._entries):
                try:
                    wc = len((await asyncio.to_thread(entry.read_text, errors="replace")).split())
                except Exception:
                    wc = 0
                widgets.append(
                    Horizontal(
                        Button(f"  {entry.name}  ({wc:,} words)",
                               id=f"entry-{i}", classes="entry-item"),
                        Button("✕", id=f"entry-del-{i}", classes="entry-del-btn"),
                        classes="entry-row",
                    )
                )
        else:
            self._entries = []
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
            self.run_worker(self._open_new_entry(journal_dir, author))
        elif bid == "btn-compile":
            self.run_worker(self._compile_with_dialog(journal_dir))
        elif bid == "btn-open-pdf":
            self.run_worker(self._open_latest_pdf(journal_dir))
        elif bid and bid.startswith("entry-del-"):
            try:
                idx = int(bid[len("entry-del-"):])
            except ValueError:
                return
            if 0 <= idx < len(self._entries):
                entry = self._entries[idx]
                self.app.push_screen(
                    ConfirmModal(
                        "Delete entry?",
                        entry.name,
                        confirm_label="Delete",
                    ),
                    lambda confirmed, p=entry: self._delete_entry(p, confirmed),
                )
        elif bid and bid.startswith("entry-") and not bid.startswith("entry-del-"):
            try:
                idx = int(bid[len("entry-"):])
            except ValueError:
                return
            if 0 <= idx < len(self._entries):
                self._open_entry(self._entries[idx])

    def _open_entry(self, entry_path: Path) -> None:
        try:
            content = entry_path.read_text(errors="replace")
        except Exception:
            log.exception("Failed to read entry: %s", entry_path)
            self.app.notify("Could not read entry — see log.", severity="error")
            return
        from modules.journal.entry_screen import JournalEntryScreen
        self.app.push_screen(
            JournalEntryScreen(content),
            lambda saved, p=entry_path: self._save_entry(p, saved),
        )

    def _delete_entry(self, entry_path: Path, confirmed: bool) -> None:
        if not confirmed:
            return
        try:
            entry_path.unlink()
            self.app.notify(f"Deleted: {entry_path.name}", severity="information")
        except Exception:
            log.exception("Failed to delete entry: %s", entry_path)
            self.app.notify("Could not delete entry — see log.", severity="error")
        self.run_worker(self._populate_content())

    async def _open_new_entry(self, journal_dir: Path, author: str) -> None:
        today      = date.today()
        year_dir   = journal_dir / "entries" / str(today.year)
        entry_path = year_dir / f"{today}.tex"

        def _create_or_open(path: Path) -> str:
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with open(path, "x", encoding="utf-8") as fh:
                    escaped = _latex_escape(author)
                    fh.write(_LATEX_TEMPLATE_SIMPLE % (today, escaped, today))
            except FileExistsError:
                pass
            return path.read_text(errors="replace")

        try:
            content = await asyncio.to_thread(_create_or_open, entry_path)
        except Exception:
            log.exception("Failed to create journal entry: %s", entry_path)
            self.app.notify("Could not create entry — see log.", severity="error")
            return

        from modules.journal.entry_screen import JournalEntryScreen
        self.app.push_screen(
            JournalEntryScreen(content),
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

    async def _open_latest_pdf(self, journal_dir: Path) -> None:
        pdfs = await asyncio.to_thread(
            lambda: sorted(journal_dir.rglob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
        )
        if pdfs:
            from nexus.core.platform import open_path
            await self._run_cmd(open_path(pdfs[0]))
        else:
            self.app.notify("No PDF found — compile first.", severity="warning")

    async def _compile_with_dialog(self, journal_dir: Path) -> None:
        entries_dir = journal_dir / "entries"
        exists = await asyncio.to_thread(entries_dir.exists)
        if not exists:
            self.app.notify("No entries directory found.", severity="warning")
            return
        entries = await asyncio.to_thread(
            lambda: sorted(entries_dir.rglob("*.tex"), key=lambda p: p.stat().st_mtime, reverse=True)
        )
        if not entries:
            self.app.notify("No .tex entries found.", severity="warning")
            return

        self.app.push_screen(
            CompileSelectModal(entries),
            lambda selected: self._do_compile_selected(selected, journal_dir),
        )

    def _do_compile_selected(self, selected: list | None, journal_dir: Path) -> None:
        if not selected:
            return
        self.run_worker(self._compile_entries(selected, journal_dir))

    async def _compile_entries(self, entries: list[Path], journal_dir: Path) -> None:
        ui_log = self.query_one("#output-log", Log)
        out_dir = journal_dir / "compiled" / str(date.today())
        await asyncio.to_thread(out_dir.mkdir, parents=True, exist_ok=True)

        compiled = 0
        for entry in entries:
            ui_log.write_line(f"$ pdflatex -interaction=nonstopmode {entry.name}")
            try:
                proc = await asyncio.create_subprocess_exec(
                    "pdflatex", "-interaction=nonstopmode", str(entry),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    cwd=str(entry.parent),
                )
                if proc.stdout is None:
                    log.error("subprocess stdout is None for %s", entry)
                    continue
                error_lines: list[str] = []
                async for raw in proc.stdout:
                    line = raw.decode(errors="replace").rstrip()
                    ui_log.write_line(line)
                    if line.startswith("!"):
                        error_lines.append(line)
                await proc.wait()
                pdf = entry.with_suffix(".pdf")
                if pdf.exists():
                    import shutil as _sh
                    dest_pdf = out_dir / pdf.name
                    await asyncio.to_thread(_sh.copy2, str(pdf), str(dest_pdf))
                    compiled += 1
                    ui_log.write_line(f"  → {dest_pdf}")
                if error_lines:
                    for e in error_lines[:3]:
                        ui_log.write_line(f"  ⚠ {e}")
            except FileNotFoundError:
                ui_log.write_line("✗ pdflatex not found — install a TeX distribution.")
                self.app.notify("pdflatex not found.", severity="error")
                return
            except Exception:
                log.exception("pdflatex failed for %s", entry)
                ui_log.write_line(f"✗ Error compiling {entry.name}")

        if compiled:
            self.app.notify(f"Compiled {compiled} entries → {out_dir}", severity="information")
        else:
            self.app.notify("No PDFs produced — check log for errors.", severity="warning")
