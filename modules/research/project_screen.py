from __future__ import annotations
import asyncio
import re
from datetime import date
from pathlib import Path

from textual.app import ComposeResult
from textual.widgets import Label, Button, Log
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.core.project_manager import ProjectInfo
from nexus.ui.base_project_screen import BaseProjectScreen, InputModal, _screen_css
from nexus.ui.text_editor_screen import TextEditorScreen

log = get("research.project_screen")


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "note"


def _first_line(path: Path) -> str:
    try:
        return path.read_text(errors="replace").splitlines()[0].lstrip("#").strip()
    except Exception:
        return ""


class ResearchProjectScreen(BaseProjectScreen):
    MODULE_KEY   = "research"
    MODULE_LABEL = "RESEARCH"
    SETUP_FIELDS = [
        {"id": "topic",     "label": "Research topic",
         "placeholder": "e.g. Machine learning interpretability"},
        {"id": "notes_dir", "label": "Notes directory",
         "placeholder": "~/research/notes", "type": "dir"},
        {"id": "format",    "label": "Note format (markdown / latex)",
         "placeholder": "markdown"},
    ]

    DEFAULT_CSS = _screen_css("ResearchProjectScreen") + """
    .note-item { width: 1fr; height: 2; border: none; background: transparent;
                 color: #8080AA; text-align: left; margin: 0; }
    .note-item:hover { background: #2D1B4E; color: #E0E0FF; }
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
            Button("New Note",    id="btn-new-note",    variant="primary"),
            Button("Fetch URL",   id="btn-fetch-url"),
            Button("Search",      id="btn-search"),
            Button("Export URLs", id="btn-export-urls"),
            Button("Export All",  id="btn-export-all"),
            Button("Refresh",     id="btn-refresh"),
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
            notes = await asyncio.to_thread(lambda: sorted(
                notes_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True
            ))
            widgets.append(
                Horizontal(
                    Label("Notes:", classes="info-key"),
                    Label(str(len(notes)), classes="info-val"),
                    classes="info-row",
                )
            )
            self._notes = notes[:20]
            widgets.append(Label("Recent notes (click to edit):", classes="section-label"))
            for i, note in enumerate(self._notes):
                first = await asyncio.to_thread(_first_line, note)
                display = f"  {note.name}" + (f" — {first}" if first else "")
                widgets.append(Button(display, id=f"note-{i}", classes="note-item"))
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
        elif bid == "btn-export-urls":
            self.run_worker(self._run_cmd(["grep", "-rh", "http", str(notes_dir)]))
        elif bid == "btn-export-all":
            self.run_worker(self._export_all(notes_dir))
        elif bid == "btn-fetch-url":
            self.app.push_screen(
                InputModal("Fetch URL", "Enter URL to fetch and save as a note:", "https://"),
                lambda url: self.run_worker(self._fetch_url(url, notes_dir)) if url else None,
            )
        elif bid == "btn-refresh":
            self.run_worker(self._populate_content())
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

    async def _fetch_url(self, url: str | None, notes_dir: Path) -> None:
        if not url:
            return
        import httpx, re as _re
        try:
            ui_log = self.query_one("#output-log", Log)
        except Exception:
            return
        ui_log.write_line(f"$ GET {url}")
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

    async def _export_all(self, notes_dir: Path) -> None:
        from textual.widgets import Log as _Log
        ui_log = self.query_one("#output-log", _Log)
        notes = sorted(notes_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not notes:
            self.app.notify("No notes to export.", severity="warning")
            return
        out = notes_dir / "export-all.md"
        try:
            parts = [await asyncio.to_thread(n.read_text, errors="replace") for n in notes]
            combined = "\n\n---\n\n".join(parts)
            await asyncio.to_thread(out.write_text, combined)
            ui_log.write_line(f"✓ Exported {len(notes)} notes → {out.name}")
            self.app.notify(f"Exported {len(notes)} notes to {out.name}")
        except Exception:
            log.exception("Export all failed")
            self.app.notify("Export failed — see log.", severity="error")
