from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from textual.app import ComposeResult
from textual.css.query import NoMatches
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Header, Footer, Label, Button, TextArea,
    ListView, ListItem,
)
from textual.containers import Vertical, Horizontal, ScrollableContainer

from nexus.core.project_manager import ProjectInfo
from nexus.core.config_manager import load_project_config
from nexus.core.logger import get

log = get("codex.project_screen")

_SOURCES = ["journal", "notes", "research", "org", "youtube"]
_EXTS    = {".md", ".tex", ".txt"}


def _get_codex_sources(project: ProjectInfo) -> dict[str, list[Path]]:
    """Return {source_id: [file, ...]} for all active source modules."""
    cfg   = load_project_config(project.slug)
    result: dict[str, list[Path]] = {}

    active = set(project.modules)

    if "journal" in active:
        jdir_str = cfg.get("journal", {}).get("journal_dir", "")
        if jdir_str:
            jdir = Path(jdir_str).expanduser()
            result["journal"] = sorted(jdir.rglob("*.tex")) if jdir.is_dir() else []
        else:
            # default subdir
            jdir = project.path / "journal"
            result["journal"] = sorted(jdir.rglob("*.tex")) if jdir.is_dir() else []

    if "notes" in active:
        ndir = project.path / "data" / "notes"
        result["notes"] = sorted(ndir.glob("*.md")) if ndir.is_dir() else []

    if "research" in active:
        rdir_str = cfg.get("research", {}).get("notes_dir", "")
        rdir = Path(rdir_str).expanduser() if rdir_str else project.path / "notes"
        result["research"] = sorted(rdir.rglob("*.md")) if rdir.is_dir() else []

    if "org" in active:
        odir_str = cfg.get("org", {}).get("output_dir", "")
        odir = Path(odir_str).expanduser() if odir_str else project.path / "plans"
        result["org"] = sorted(odir.rglob("*.md")) if odir.is_dir() else []

    if "youtube" in active:
        ydir_str = cfg.get("youtube", {}).get("output_dir", "")
        if ydir_str:
            ydir = Path(ydir_str).expanduser()
            result["youtube"] = sorted(
                f for f in ydir.rglob("*") if f.suffix in {".txt", ".md"}
            ) if ydir.is_dir() else []

    return result


# ── Reorder modal ─────────────────────────────────────────────────────────────

class _ReorderModal(ModalScreen[list[Path] | None]):
    """Shows selected files in order; user can move items up/down before export."""

    DEFAULT_CSS = """
    _ReorderModal { align: center middle; }
    #rm-dialog {
        background: $theme-surface; border: solid $theme-border;
        padding: 1 2; width: 72; height: 80%;
    }
    #rm-title  { color: $theme-border; text-style: bold; height: 2; }
    #rm-scroll { height: 1fr; border: solid $theme-border-dim; padding: 0 1; }
    .rm-item   { height: 1; }
    #rm-btns   { height: 3; margin-top: 1; }
    #rm-btns Button { margin-right: 1; }
    #rm-arrows { height: 3; margin-top: 1; }
    #rm-arrows Button { margin-right: 1; }
    """

    def __init__(self, files: list[Path]) -> None:
        super().__init__()
        self._files = list(files)
        self._cursor = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="rm-dialog"):
            yield Label("Order files for PDF — use ↑/↓ to rearrange", id="rm-title")
            with ScrollableContainer(id="rm-scroll"):
                for i, f in enumerate(self._files):
                    yield Label(f"  {i+1}. {f.name}", id=f"rm-item-{i}", classes="rm-item")
            with Horizontal(id="rm-arrows"):
                yield Button("↑ Up",   id="rm-up")
                yield Button("↓ Down", id="rm-down")
            with Horizontal(id="rm-btns"):
                yield Button("Export to PDF", id="rm-confirm", variant="primary")
                yield Button("Cancel",        id="rm-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id
        if bid == "rm-cancel":
            self.dismiss(None)
        elif bid == "rm-confirm":
            self.dismiss(self._files)
        elif bid == "rm-up" and self._cursor > 0:
            i = self._cursor
            self._files[i - 1], self._files[i] = self._files[i], self._files[i - 1]
            self._cursor -= 1
            self._refresh_labels()
        elif bid == "rm-down" and self._cursor < len(self._files) - 1:
            i = self._cursor
            self._files[i], self._files[i + 1] = self._files[i + 1], self._files[i]
            self._cursor += 1
            self._refresh_labels()

    def _refresh_labels(self) -> None:
        for i, f in enumerate(self._files):
            try:
                lbl = self.query_one(f"#rm-item-{i}", Label)
                prefix = "► " if i == self._cursor else "  "
                lbl.update(f"{prefix}{i+1}. {f.name}")
            except NoMatches:
                pass


# ── Codex screen ──────────────────────────────────────────────────────────────

class ProjectScreen(Screen):
    """Document explorer and PDF compiler."""

    BINDINGS = [
        ("escape", "dismiss", "Back"),
        ("r",      "refresh", "Refresh"),
    ]

    DEFAULT_CSS = """
    ProjectScreen { background: $theme-bg; }
    ProjectScreen Header { background: $theme-surface; color: $theme-border; }
    ProjectScreen Footer { background: $theme-surface; color: $theme-accent2; }

    #top-bar {
        height: 3; background: $theme-surface; padding: 0 2;
        border-bottom: solid $theme-border-dim;
    }
    #project-title { color: $theme-border; text-style: bold; width: 1fr; }
    #checked-count { color: $theme-accent2; width: 12; }

    #body { height: 1fr; }

    #file-panel {
        width: 40%; border-right: solid $theme-border-dim;
    }
    #file-scroll { height: 1fr; }

    .source-header {
        color: $theme-accent2; text-style: bold;
        height: 1; padding: 0 1; margin-top: 1;
    }
    .file-item {
        height: 1; padding: 0 1;
        color: $theme-text-dim;
    }
    .file-item:hover  { color: $theme-text; background: $theme-surface; }
    .file-item:focus  { color: $theme-text; background: $theme-surface;
                        border-left: solid $theme-accent2; }
    .file-item.checked { color: $theme-text; }
    .file-checked-mark { color: $theme-accent2; width: 3; }

    #preview-panel { width: 1fr; height: 1fr; }
    #preview-area  { height: 1fr; }

    #bottom-bar {
        height: 3; background: $theme-surface; padding: 0 2;
        border-top: solid $theme-border-dim;
    }
    #btn-pdf { width: 14; }
    #bottom-info { color: $theme-text-dim; width: 1fr; }
    """

    def __init__(self, project: ProjectInfo) -> None:
        super().__init__()
        self.project   = project
        self._sources: dict[str, list[Path]] = {}
        self._checked: set[str] = set()   # str(path) keys
        self._preview_file: Path | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="top-bar"):
            yield Label(f"Codex — {self.project.name}", id="project-title")
            yield Label("0 checked", id="checked-count")
        with Horizontal(id="body"):
            with Vertical(id="file-panel"):
                with ScrollableContainer(id="file-scroll"):
                    yield Label("Loading…", id="file-placeholder")
            with Vertical(id="preview-panel"):
                yield TextArea("", id="preview-area", read_only=True)
        with Horizontal(id="bottom-bar"):
            yield Button("To PDF", id="btn-pdf", variant="primary")
            yield Label("Select files then click To PDF", id="bottom-info")
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._load_sources())

    async def _load_sources(self) -> None:
        self._sources = await asyncio.to_thread(_get_codex_sources, self.project)
        await self._rebuild_file_list()

    async def _rebuild_file_list(self) -> None:
        scroll = self.query_one("#file-scroll", ScrollableContainer)
        await scroll.remove_children()

        widgets: list = []
        total = 0
        for source_id, files in self._sources.items():
            if not files:
                continue
            widgets.append(Label(f"── {source_id.title()} ──", classes="source-header"))
            for f in files:
                total += 1
                fid = f"fitem-{total}"
                is_checked = str(f) in self._checked
                mark = "☑" if is_checked else "☐"
                cls = "file-item checked" if is_checked else "file-item"
                with Horizontal(classes=cls, id=fid):
                    widgets[-1]  # just reference; we mount below
                btn = Button(f"{mark} {f.name}", id=f"fbtn-{total}", classes=cls)
                btn._codex_path = str(f)  # type: ignore[attr-defined]
                widgets.append(btn)

        if not widgets:
            widgets.append(Label(
                "No source files found.\n\n"
                "Activate Journal, Notes, Research, Org or YouTube modules\n"
                "and add some content first.",
                id="file-placeholder",
            ))

        await scroll.mount(*widgets)
        self._update_count_label()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id or ""

        if bid == "btn-pdf":
            self._start_pdf_export()
            return

        if bid.startswith("fbtn-"):
            path_str = getattr(event.button, "_codex_path", None)
            if path_str is None:
                return
            if path_str in self._checked:
                self._checked.discard(path_str)
                event.button.label = f"☐ {Path(path_str).name}"
                event.button.remove_class("checked")
            else:
                self._checked.add(path_str)
                event.button.label = f"☑ {Path(path_str).name}"
                event.button.add_class("checked")
            self._update_count_label()
            self._show_preview(Path(path_str))

    def _show_preview(self, path: Path) -> None:
        try:
            text = path.read_text(errors="replace")
        except Exception:
            text = f"(Could not read {path.name})"
        try:
            area = self.query_one("#preview-area", TextArea)
            area.load_text(text)
        except NoMatches:
            pass

    def _update_count_label(self) -> None:
        n = len(self._checked)
        try:
            self.query_one("#checked-count", Label).update(f"{n} checked")
        except NoMatches:
            pass

    def _start_pdf_export(self) -> None:
        if not self._checked:
            self.app.notify("Select at least one file first.", severity="warning")
            return
        if not shutil.which("pandoc"):
            self.app.notify("pandoc is not installed.", severity="error")
            return

        # Collect files in discovery order (preserves source grouping)
        ordered: list[Path] = []
        for files in self._sources.values():
            for f in files:
                if str(f) in self._checked:
                    ordered.append(f)

        self.app.push_screen(_ReorderModal(ordered), self._run_pandoc)

    def _run_pandoc(self, files: list[Path] | None) -> None:
        if not files:
            return
        out_dir = self.project.path / "codex"
        out_dir.mkdir(parents=True, exist_ok=True)

        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_pdf = out_dir / f"codex_{ts}.pdf"

        cmd = ["pandoc"] + [str(f) for f in files] + [
            "-o", str(out_pdf),
            "--pdf-engine=xelatex",
        ]
        self.run_worker(self._exec_pandoc(cmd, out_pdf))

    async def _exec_pandoc(self, cmd: list[str], out_pdf: Path) -> None:
        self.app.notify("Generating PDF…", severity="information")
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            if proc.stdout is None:
                self.app.notify("pandoc stdout unavailable.", severity="error")
                return
            output = await proc.stdout.read()
            await proc.wait()
            if proc.returncode == 0:
                self.app.notify(f"PDF saved: {out_pdf.name}", severity="information")
            else:
                err = output.decode(errors="replace")[:200]
                log.error("pandoc failed: %s", err)
                self.app.notify("PDF generation failed — see log.", severity="error")
        except Exception:
            log.exception("Failed to run pandoc")
            self.app.notify("pandoc error — see log.", severity="error")

    def action_dismiss(self, result=None) -> None:
        self.dismiss(result)

    def action_refresh(self) -> None:
        self.run_worker(self._load_sources())
