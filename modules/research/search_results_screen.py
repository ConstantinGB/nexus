from __future__ import annotations
import asyncio
import re
from datetime import date
from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Label, Button, TextArea
from textual.containers import Vertical, Horizontal, ScrollableContainer

from nexus.core.logger import get

log = get("research.search_results")


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "result"


def _build_note_text(result: dict, body: str, source: str) -> str:
    url       = result.get("url") or ""
    published = result.get("publishedAt") or ""
    origin    = result.get("source") or source
    title     = result.get("title") or "result"
    pub_line  = f"published: {published}\n" if published else ""
    return (
        f"---\ndate: {date.today()}\nsource: {url}\n"
        f"{pub_line}tags: []\norigin: {origin}\n---\n\n"
        f"# {title}\n\n{body}\n"
    )


def _extract_body(result: dict, source: str) -> str:
    """Build the plain-text body for a News result (no network call needed)."""
    description = result.get("description") or ""
    content     = result.get("content") or ""
    content     = re.sub(r"\s*\[\+\d+ chars\]$", "", content).strip()
    text        = "\n\n".join(p for p in [description, content] if p)
    return text or f"Full article at: {result.get('url', '')}"


# ── Article preview screen ─────────────────────────────────────────────────────

class ArticlePreviewScreen(Screen):
    """Read-only full-text preview of a search result with an optional Save action."""

    DEFAULT_CSS = """
    ArticlePreviewScreen { background: #1A0A2E; }
    #ap-top {
        height: 3; background: #2D1B4E;
        border-bottom: solid #3A2260; padding: 0 2;
    }
    #ap-title { color: #00B4FF; text-style: bold; width: 1fr; }
    #ap-top Button { margin-left: 1; }
    #ap-body { height: 1fr; }
    """

    BINDINGS = [("escape", "close", "Close")]

    def __init__(
        self,
        result: dict,
        content: str,
        notes_dir: Path,
        source: str,
    ) -> None:
        super().__init__()
        self._result   = result
        self._content  = content
        self._notes_dir = notes_dir
        self._source   = source

    def compose(self) -> ComposeResult:
        title = self._result.get("title") or "Article"
        with Horizontal(id="ap-top"):
            yield Label(title, id="ap-title")
            yield Button("Save",  id="ap-save",  variant="primary")
            yield Button("Close", id="ap-close")
        yield TextArea(
            self._content, id="ap-body",
            read_only=True, soft_wrap=True, show_line_numbers=False,
        )

    def on_mount(self) -> None:
        try:
            self.query_one("#ap-body", TextArea).focus()
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "ap-close":
            self.action_close()
        elif event.button.id == "ap-save":
            self.run_worker(self._save(event.button))

    def action_close(self) -> None:
        self.app.pop_screen()

    async def _save(self, button: Button) -> None:
        title = self._result.get("title") or "result"
        slug  = _slugify(title)
        dest  = self._notes_dir / f"{slug}.md"
        try:
            await asyncio.to_thread(self._notes_dir.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(
                dest.write_text,
                _build_note_text(self._result, self._content, self._source),
            )
            try:
                button.label    = "Saved ✓"
                button.disabled = True
            except Exception:
                pass
            self.app.notify(f"Saved: {dest.name}", severity="information")
        except Exception as exc:
            log.exception("Save failed in preview for %s", title)
            self.app.notify(f"Save failed: {exc}", severity="error")


# ── Search results screen ──────────────────────────────────────────────────────

class SearchResultsScreen(Screen):
    DEFAULT_CSS = """
    SearchResultsScreen { background: #1A0A2E; }
    #sr-top {
        height: 3; background: #2D1B4E;
        border-bottom: solid #3A2260; padding: 0 2;
    }
    #sr-title { color: #00B4FF; text-style: bold; width: 1fr; }
    #sr-close { width: 10; }
    #sr-body { height: 1fr; padding: 1 2; }
    #sr-results { height: auto; }
    .sr-row {
        height: 5; margin-bottom: 1;
        border: solid #3A2260; padding: 0 1;
    }
    .sr-info { width: 1fr; height: 5; }
    .sr-title-lbl { color: #00FF88; height: 2; }
    .sr-snippet { color: #8080AA; height: 2; overflow: hidden; }
    .sr-btns { width: 26; height: 5; }
    .sr-view-btn { width: 12; height: 5; }
    .sr-dl-btn   { width: 12; height: 5; }
    #sr-footer { height: 3; align: center middle; }
    #sr-load-more { width: 20; }
    #sr-status { height: 1; color: #8080AA; width: 1fr; margin-left: 2; }
    """

    BINDINGS = [("escape", "app.pop_screen", "Close")]

    def __init__(
        self,
        results: list[dict],
        source: str,
        query: str,
        notes_dir: Path,
        api_key: str = "",
        page: int = 1,
    ) -> None:
        super().__init__()
        self._results: list[dict] = list(results)
        self._source  = source
        self._query   = query
        self._notes_dir = notes_dir
        self._api_key = api_key
        self._page    = page

    def compose(self) -> ComposeResult:
        with Horizontal(id="sr-top"):
            yield Label(
                f"Results: {self._query!r}  [{self._source}]", id="sr-title"
            )
            yield Button("Close", id="sr-close")
        with ScrollableContainer(id="sr-body"):
            yield Vertical(id="sr-results")
            with Horizontal(id="sr-footer"):
                yield Button("Load More", id="sr-load-more")
                yield Label("", id="sr-status")

    def on_mount(self) -> None:
        self.run_worker(self._render_results(self._results, offset=0))

    async def _render_results(self, results: list[dict], offset: int = 0) -> None:
        try:
            container = self.query_one("#sr-results", Vertical)
        except Exception:
            return
        widgets = []
        for i, r in enumerate(results):
            idx     = offset + i
            title   = r.get("title") or ""
            snippet = (r.get("description") or r.get("summary") or "")[:200]
            widgets.append(
                Horizontal(
                    Vertical(
                        Label(title,   classes="sr-title-lbl"),
                        Label(snippet, classes="sr-snippet"),
                        classes="sr-info",
                    ),
                    Vertical(
                        Button("View",     id=f"sr-view-{idx}", classes="sr-view-btn"),
                        Button("Download", id=f"sr-dl-{idx}",   classes="sr-dl-btn"),
                        classes="sr-btns",
                    ),
                    classes="sr-row",
                )
            )
        if widgets:
            await container.mount(*widgets)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id or ""
        if bid == "sr-close":
            self.app.pop_screen()
        elif bid == "sr-load-more":
            self.run_worker(self._load_more())
        elif bid.startswith("sr-view-"):
            try:
                idx = int(bid[len("sr-view-"):])
            except ValueError:
                return
            if 0 <= idx < len(self._results):
                self.run_worker(self._view(idx, event.button))
        elif bid.startswith("sr-dl-"):
            try:
                idx = int(bid[len("sr-dl-"):])
            except ValueError:
                return
            if 0 <= idx < len(self._results):
                self.run_worker(self._download(idx, event.button))

    async def _set_status(self, msg: str) -> None:
        try:
            self.query_one("#sr-status", Label).update(msg)
        except Exception:
            pass

    async def _load_more(self) -> None:
        from modules.research.api_client import search_news, search_wiki
        await self._set_status("Loading…")
        self._page += 1
        try:
            if self._source == "News":
                new_results = await search_news(
                    self._query, self._api_key, page=self._page
                )
            else:
                new_results = await search_wiki(self._query, limit=10)
        except Exception as exc:
            log.exception("Load more failed")
            await self._set_status(f"✗ {exc}")
            return
        offset = len(self._results)
        self._results.extend(new_results)
        await self._render_results(new_results, offset=offset)
        await self._set_status(f"+{len(new_results)} results")

    async def _fetch_body(self, r: dict) -> str:
        """Fetch article body text (network call for Wikipedia, local for News)."""
        from modules.research.api_client import fetch_wiki_full_text
        if self._source == "News":
            return _extract_body(r, self._source)
        title    = r.get("title") or ""
        language = r.get("language", "en")
        return await fetch_wiki_full_text(title, language=language)

    async def _view(self, idx: int, button: Button) -> None:
        r = self._results[idx]
        try:
            button.label    = "Loading…"
            button.disabled = True
        except Exception:
            pass
        try:
            text = await self._fetch_body(r)
        except Exception as exc:
            log.exception("Fetch failed for view: %s", r.get("title"))
            try:
                button.label    = "View"
                button.disabled = False
            except Exception:
                pass
            self.app.notify(f"Failed to load article: {exc}", severity="error")
            return
        try:
            button.label    = "View"
            button.disabled = False
        except Exception:
            pass
        self.app.push_screen(
            ArticlePreviewScreen(
                result=r,
                content=text,
                notes_dir=self._notes_dir,
                source=self._source,
            )
        )

    async def _download(self, idx: int, button: Button) -> None:
        r = self._results[idx]
        title = r.get("title") or "result"
        slug  = _slugify(title)
        dest  = self._notes_dir / f"{slug}.md"
        try:
            text = await self._fetch_body(r)
        except Exception as exc:
            log.exception("Download failed for %s", title)
            try:
                button.label = "Failed ✗"
            except Exception:
                pass
            self.app.notify(f"Download failed: {exc}", severity="error")
            return
        try:
            await asyncio.to_thread(self._notes_dir.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(
                dest.write_text,
                _build_note_text(r, text, self._source),
            )
            try:
                button.label    = "Saved ✓"
                button.disabled = True
            except Exception:
                pass
            self.app.notify(f"Saved: {dest.name}", severity="information")
        except Exception as exc:
            log.exception("Write failed for %s", title)
            try:
                button.label = "Failed ✗"
            except Exception:
                pass
            self.app.notify(f"Save failed: {exc}", severity="error")
