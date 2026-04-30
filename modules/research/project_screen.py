from __future__ import annotations
import asyncio
import os
import re
import tempfile
from datetime import date
from pathlib import Path

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, Button, Log, Checkbox
from textual.containers import Vertical, Horizontal, ScrollableContainer

from nexus.core.logger import get
from nexus.core.project_manager import ProjectInfo
from nexus.ui.base_project_screen import BaseProjectScreen, ConfirmModal, InputModal, _screen_css
from nexus.ui.text_editor_screen import TextEditorScreen

log = get("research.project_screen")


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "note"


def _first_line(path: Path) -> str:
    """Return the first meaningful title line, skipping YAML frontmatter."""
    try:
        lines = path.read_text(errors="replace").splitlines()
        in_front = len(lines) > 0 and lines[0].strip() == "---"
        for i, line in enumerate(lines):
            if i == 0 and in_front:
                continue
            if in_front and line.strip() == "---":
                in_front = False
                continue
            if in_front:
                continue
            stripped = line.lstrip("#").strip()
            if stripped:
                return stripped
        return ""
    except Exception:
        return ""


class ExportAllModal(ModalScreen[str | None]):
    """Ask user to choose Markdown or PDF before exporting all notes."""

    DEFAULT_CSS = """
    ExportAllModal { align: center middle; }
    #eam-dialog {
        background: #2D1B4E; border: solid #00B4FF;
        padding: 1 2; width: 52; height: auto;
    }
    #eam-title  { color: #00B4FF; text-style: bold; height: 2; }
    #eam-hint   { color: #8080AA; height: 2; margin-bottom: 1; }
    #eam-btns   { height: 3; }
    #eam-btns Button { margin-right: 1; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="eam-dialog"):
            yield Label("Export All Notes", id="eam-title")
            yield Label("Choose export format:", id="eam-hint")
            with Horizontal(id="eam-btns"):
                yield Button("Markdown", id="eam-md",  variant="primary")
                yield Button("PDF",      id="eam-pdf")
                yield Button("Cancel",   id="eam-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id
        if bid == "eam-md":
            self.dismiss("md")
        elif bid == "eam-pdf":
            self.dismiss("pdf")
        else:
            self.dismiss(None)


class ExportDocModal(ModalScreen[tuple[str, list[Path]] | None]):
    """Checkbox list of notes; user selects which ones to combine and export."""

    DEFAULT_CSS = """
    ExportDocModal { align: center middle; }
    #edm-dialog {
        background: #2D1B4E; border: solid #00B4FF;
        padding: 1 2; width: 70; height: 80%;
    }
    #edm-title    { color: #00B4FF; text-style: bold; height: 2; }
    #edm-list     { height: 1fr; border: solid #3A2260; padding: 0 1; }
    #edm-btns     { height: 3; margin-top: 1; }
    #edm-btns Button { margin-right: 1; }
    """

    def __init__(self, notes: list[Path]) -> None:
        super().__init__()
        self._notes = notes

    def compose(self) -> ComposeResult:
        with Vertical(id="edm-dialog"):
            yield Label("Export Documents", id="edm-title")
            with ScrollableContainer(id="edm-list"):
                for i, note in enumerate(self._notes):
                    yield Checkbox(note.stem, value=True, id=f"edm-chk-{i}")
            with Horizontal(id="edm-btns"):
                yield Button("Export MD",  id="edm-md",     variant="primary")
                yield Button("Export PDF", id="edm-pdf")
                yield Button("Cancel",     id="edm-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id
        if bid == "edm-cancel":
            self.dismiss(None)
            return
        fmt = "md" if bid == "edm-md" else "pdf"
        checked: list[Path] = []
        for i, note in enumerate(self._notes):
            try:
                if self.query_one(f"#edm-chk-{i}", Checkbox).value:
                    checked.append(note)
            except Exception:
                pass
        self.dismiss((fmt, checked) if checked else None)


class ResearchProjectScreen(BaseProjectScreen):
    MODULE_KEY        = "research"
    MODULE_LABEL      = "RESEARCH"
    REQUIRED_BINARIES = [("rg", "ripgrep")]
    SETUP_FIELDS      = [
        {"id": "topic",     "label": "Research topic",
         "placeholder": "e.g. Machine learning interpretability"},
        {"id": "notes_dir", "label": "Notes directory",
         "placeholder": "~/research/notes", "type": "dir"},
        {"id": "format",    "label": "Note format (markdown / latex)",
         "placeholder": "markdown"},
    ]

    DEFAULT_CSS = _screen_css("ResearchProjectScreen") + """
    .note-row    { height: 3; width: 1fr; }
    .note-item   { width: 1fr; height: 3; border: none; background: transparent;
                   color: #8080AA; text-align: left; margin: 0; }
    .note-item:hover { background: #2D1B4E; color: #E0E0FF; }
    .note-pdf-btn { width: 7; height: 3; background: transparent;
                    border: none; color: #4080AA; margin: 0; }
    .note-pdf-btn:hover { color: #00B4FF; background: #1A2D4E; }
    .note-del-btn { width: 5; height: 3; background: transparent;
                    border: none; color: #553333; margin: 0; }
    .note-del-btn:hover { color: #FF4444; background: #2D1B1B; }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._notes: list[Path] = []

    # ── Before-save hook ──────────────────────────────────────────────────────

    def _on_before_save(self, data: dict) -> dict:
        notes_dir = Path(data.get("notes_dir", "")).expanduser()
        if notes_dir and not notes_dir.exists():
            notes_dir.mkdir(parents=True, exist_ok=True)
            self.app.notify(f"Created: {notes_dir}", severity="information")
        return {}

    # ── Action buttons ────────────────────────────────────────────────────────

    def _compose_action_buttons(self) -> list:
        return [
            Button("New Note",   id="btn-new-note",   variant="primary"),
            Button("Fetch URL",  id="btn-fetch-url"),
            Button("Search",     id="btn-search"),
            Button("Export Doc", id="btn-export-doc"),
            Button("Export All", id="btn-export-all"),
            Button("Refresh",    id="btn-refresh"),
        ]

    # ── Main content ──────────────────────────────────────────────────────────

    async def _populate_content(self) -> None:
        area = self.query_one("#content-area", Vertical)
        await area.remove_children()

        topic     = self._mod.get("topic", "")
        notes_dir = Path(self._mod.get("notes_dir", "")).expanduser()

        widgets: list = [
            Horizontal(
                Label("Topic:", classes="info-key"),
                Label(topic,    classes="info-val"),
                classes="info-row",
            ),
        ]

        if notes_dir.exists():
            all_notes = await asyncio.to_thread(lambda: sorted(
                [n for n in notes_dir.glob("*.md") if n.name != "CLAUDE.md"],
                key=lambda p: p.stat().st_mtime, reverse=True,
            ))
            widgets.append(
                Horizontal(
                    Label("Notes:", classes="info-key"),
                    Label(str(len(all_notes)), classes="info-val"),
                    classes="info-row",
                )
            )
            self._notes = all_notes[:20]
            widgets.append(Label("Recent notes (click to edit):", classes="section-label"))
            for i, note in enumerate(self._notes):
                first = await asyncio.to_thread(_first_line, note)
                stem = note.stem
                display = f"  {stem}" + (f" — {first}" if first else "")
                widgets.append(
                    Horizontal(
                        Button(display,  id=f"note-{i}",     classes="note-item"),
                        Button("PDF",    id=f"note-pdf-{i}", classes="note-pdf-btn"),
                        Button("✕",      id=f"note-del-{i}", classes="note-del-btn"),
                        classes="note-row",
                    )
                )
        else:
            widgets.append(Label(f"Notes directory not found: {notes_dir}", classes="status-err"))
            widgets.append(Label("Create the directory and add .md files to get started.", classes="hint"))

        await area.mount(*widgets)

    def _primary_folder(self) -> Path | None:
        p = Path(self._mod.get("notes_dir", "")).expanduser()
        return p if str(p) != "." else None

    # ── Button handler ────────────────────────────────────────────────────────

    def _handle_action(self, bid: str | None) -> None:
        notes_dir = Path(self._mod.get("notes_dir", "")).expanduser()

        if bid == "btn-new-note":
            self.app.push_screen(
                InputModal("New Note", "Note title or filename:", "my-note"),
                lambda title: self._create_note(title, notes_dir),
            )
        elif bid == "btn-search":
            self.app.push_screen(
                InputModal("Search", "Search query:", "keyword"),
                lambda q: self._do_search(q, notes_dir),
            )
        elif bid == "btn-export-doc":
            if not self._notes:
                self.app.notify("No notes to export.", severity="warning")
                return
            self.app.push_screen(
                ExportDocModal(list(self._notes)),
                lambda result: self.run_worker(
                    self._export_notes(notes_dir, result[0], result[1])
                ) if result else None,
            )
        elif bid == "btn-export-all":
            self.app.push_screen(
                ExportAllModal(),
                lambda fmt: self.run_worker(self._export_notes(notes_dir, fmt)) if fmt else None,
            )
        elif bid == "btn-fetch-url":
            self.app.push_screen(
                InputModal("Fetch URL", "Enter URL to fetch and save as a note:", "https://"),
                lambda url: self.run_worker(self._fetch_url(url, notes_dir)) if url else None,
            )
        elif bid == "btn-refresh":
            self.run_worker(self._populate_content())
        elif bid and bid.startswith("note-pdf-"):
            try:
                idx = int(bid[len("note-pdf-"):])
            except ValueError:
                return
            if 0 <= idx < len(self._notes):
                self.run_worker(self._export_note_pdf(self._notes[idx]))
        elif bid and bid.startswith("note-del-"):
            try:
                idx = int(bid[len("note-del-"):])
            except ValueError:
                return
            if 0 <= idx < len(self._notes):
                note = self._notes[idx]
                self.app.push_screen(
                    ConfirmModal("Delete note?", note.name),
                    lambda confirmed, p=note: self._delete_note(p) if confirmed else None,
                )
        elif bid and bid.startswith("note-"):
            try:
                idx = int(bid.split("-", 1)[1])
            except ValueError:
                return
            if 0 <= idx < len(self._notes):
                self._open_note(self._notes[idx])

    def _do_search(self, q: str | None, notes_dir: Path) -> None:
        if not q:
            return
        import shutil
        if not shutil.which("rg"):
            self.app.notify("ripgrep (rg) is not installed — install it to use search.", severity="warning")
            return
        self.run_worker(self._run_cmd(["rg", "-n", q, str(notes_dir)]))

    def _open_note(self, note_path: Path) -> None:
        try:
            content = note_path.read_text(errors="replace")
        except Exception:
            log.exception("Failed to read note: %s", note_path)
            self.app.notify("Could not read note — see log.", severity="error")
            return
        fmt  = self._mod.get("format", "markdown")
        lang = "markdown" if fmt == "markdown" else "text"
        self.app.push_screen(
            TextEditorScreen(content, language=lang, title=note_path.name),
            lambda saved, p=note_path: self._save_note(p, saved),
        )

    def _delete_note(self, note_path: Path) -> None:
        try:
            note_path.unlink()
            self.app.notify(f"Deleted: {note_path.name}", severity="information")
        except Exception:
            log.exception("Failed to delete note: %s", note_path)
            self.app.notify("Could not delete note — see log.", severity="error")
            return
        self.run_worker(self._populate_content())

    def _save_note(self, note_path: Path, content: str | None) -> None:
        if content is None:
            return
        try:
            note_path.write_text(content)
            self.app.notify(f"Saved: {note_path.name}", severity="information")
        except Exception:
            log.exception("Failed to save note: %s", note_path)
            self.app.notify("Could not save note — see log.", severity="error")
        self.run_worker(self._populate_content())

    def _create_note(self, title: str | None, notes_dir: Path) -> None:
        if not title:
            return
        slug = _slugify(title)
        dest = notes_dir / f"{slug}.md"
        try:
            notes_dir.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                topic = self._mod.get("topic", "")
                dest.write_text(
                    f"---\ndate: {date.today()}\ntopic: {topic}\ntags: []\n---\n\n"
                    f"# {title}\n\n"
                )
        except Exception:
            log.exception("Failed to create note: %s", dest)
            self.app.notify("Could not create note — see log.", severity="error")
            return
        self._open_note(dest)

    async def _export_note_pdf(self, note_path: Path) -> None:
        import shutil
        try:
            ui_log = self.query_one("#output-log", Log)
        except Exception:
            return
        if not shutil.which("pandoc"):
            self.app.notify("pandoc not found — install pandoc for PDF export.", severity="error")
            return
        out = note_path.with_suffix(".pdf")
        try:
            ui_log.write_line(f"$ pandoc {note_path.name} -o {out.name}")
        except Exception:
            return
        proc = await asyncio.create_subprocess_exec(
            "pandoc", str(note_path), "-o", str(out),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            err = stderr.decode(errors="replace").strip()
            log.error("pandoc PDF export failed for %s: %s", note_path, err)
            try:
                ui_log.write_line(f"✗ pandoc: {err}")
            except Exception:
                pass
            hint = " (install texlive-latex-recommended)" if ".sty' not found" in err else ""
            self.app.notify(f"PDF export failed{hint}: {err[:100]}", severity="error")
            return
        try:
            ui_log.write_line(f"✓ {out.name}")
        except Exception:
            pass
        self.app.notify(f"PDF saved: {out.name}", severity="information")

    async def _export_notes(
        self,
        notes_dir: Path,
        fmt: str | None,
        notes: list[Path] | None = None,
    ) -> None:
        import shutil
        try:
            ui_log = self.query_one("#output-log", Log)
        except Exception:
            return

        if fmt is None:
            return

        if notes is None:
            notes = await asyncio.to_thread(lambda: sorted(
                [n for n in notes_dir.glob("*.md") if n.name != "CLAUDE.md"],
                key=lambda p: p.stat().st_mtime, reverse=True,
            ))

        if not notes:
            self.app.notify("No notes to export.", severity="warning")
            return

        if fmt == "pdf":
            if not shutil.which("pandoc"):
                self.app.notify("pandoc not found — install pandoc for PDF export.", severity="error")
                return
            out = notes_dir / "export-all.pdf"
            try:
                parts = [await asyncio.to_thread(n.read_text, errors="replace") for n in notes]
                combined = "\n\n---\n\n".join(parts)
                fd, tmp_path = tempfile.mkstemp(suffix=".md")
                try:
                    with os.fdopen(fd, "w") as f:
                        f.write(combined)
                    try:
                        ui_log.write_line(f"$ pandoc → {out.name}")
                    except Exception:
                        pass
                    proc = await asyncio.create_subprocess_exec(
                        "pandoc", tmp_path, "-o", str(out),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    _, stderr = await proc.communicate()
                finally:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                if proc.returncode != 0:
                    err = stderr.decode(errors="replace").strip()
                    log.error("pandoc export-all PDF failed: %s", err)
                    try:
                        ui_log.write_line(f"✗ pandoc: {err}")
                    except Exception:
                        pass
                    hint = " (install texlive-latex-recommended)" if ".sty' not found" in err else ""
                    self.app.notify(f"PDF export failed{hint}: {err[:100]}", severity="error")
                    return
                try:
                    ui_log.write_line(f"✓ Exported {len(notes)} notes → {out.name}")
                except Exception:
                    pass
                self.app.notify(f"Exported {len(notes)} notes to {out.name}")
            except Exception:
                log.exception("Export all PDF failed")
                self.app.notify("Export failed — see log.", severity="error")
        else:
            out = notes_dir / "export-all.md"
            try:
                parts = [await asyncio.to_thread(n.read_text, errors="replace") for n in notes]
                combined = "\n\n---\n\n".join(parts)
                await asyncio.to_thread(out.write_text, combined)
                try:
                    ui_log.write_line(f"✓ Exported {len(notes)} notes → {out.name}")
                except Exception:
                    pass
                self.app.notify(f"Exported {len(notes)} notes to {out.name}")
            except Exception:
                log.exception("Export all failed")
                self.app.notify("Export failed — see log.", severity="error")

    async def _fetch_url(self, url: str | None, notes_dir: Path) -> None:
        if not url:
            return
        import httpx, re as _re
        try:
            ui_log = self.query_one("#output-log", Log)
        except Exception:
            return
        try:
            ui_log.write_line(f"$ GET {url}")
        except Exception:
            return
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                resp = await client.get(url)
            resp.raise_for_status()
        except Exception as exc:
            try:
                ui_log.write_line(f"✗ {exc}")
            except Exception:
                pass
            self.app.notify(f"Fetch failed: {exc}", severity="error")
            return
        html = resp.text
        text = _re.sub(r"<[^>]+>", " ", html)
        text = _re.sub(r"[ \t]{2,}", " ", text)
        text = "\n".join(l.strip() for l in text.splitlines() if l.strip())

        slug = _slugify(_re.sub(r"https?://", "", url)[:60])
        dest = notes_dir / f"{slug}.md"
        try:
            notes_dir.mkdir(parents=True, exist_ok=True)
            dest.write_text(
                f"---\ndate: {date.today()}\nsource: {url}\ntags: []\n---\n\n"
                f"# {url}\n\n{text}\n"
            )
        except Exception as exc:
            try:
                ui_log.write_line(f"✗ Save failed: {exc}")
            except Exception:
                pass
            self.app.notify("Could not save fetched page.", severity="error")
            return
        try:
            ui_log.write_line(f"✓ Saved → {dest.name}")
        except Exception:
            pass
        self.app.notify(f"Fetched and saved: {dest.name}", severity="information")
        self.run_worker(self._populate_content())
