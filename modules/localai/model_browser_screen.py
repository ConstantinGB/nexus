from __future__ import annotations
import asyncio

import httpx
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Input, Button, Label, Log, TabbedContent, TabPane
from textual.containers import Horizontal, ScrollableContainer

from nexus.core.logger import get
from modules.localai import model_catalog

_FIT_LABELS: dict[str, tuple[str, str]] = {
    "recommended": ("★ GPU fit",   "#00FF88"),
    "fits":        ("~ GPU tight", "#FFFF44"),
    "cpu-only":    ("CPU only",    "#00B4FF"),
    "too-large":   ("✗ Too large", "#FF4444"),
}

_FIT_ORDER: dict[str, int] = {"recommended": 0, "cpu-only": 1, "fits": 2, "too-large": 3}

log = get("localai.model_browser")


import re as _re

def _san(model_id: str) -> str:
    return _re.sub(r'[^a-zA-Z0-9_-]', '-', model_id)


class ModelRow(Horizontal):
    DEFAULT_CSS = """
    ModelRow { height: 3; padding: 0 1; border-bottom: solid #241540; }
    ModelRow:hover { background: #2D1B4E; }
    ModelRow .mr-id   { width: 18; color: #E0E0FF; content-align: left middle; }
    ModelRow .mr-size { width: 6;  color: #8080AA; content-align: left middle; }
    ModelRow .mr-fit  { width: 12; content-align: left middle; }
    ModelRow .mr-fit-recommended { color: #00FF88; }
    ModelRow .mr-fit-fits        { color: #FFFF44; }
    ModelRow .mr-fit-cpu-only    { color: #00B4FF; }
    ModelRow .mr-fit-too-large   { color: #FF4444; }
    ModelRow .mr-fit-none        { color: #555555; }
    ModelRow .mr-desc { width: 1fr; color: #555588; content-align: left middle; }
    ModelRow .mr-chk  { width: 3;  color: #00FF88; content-align: left middle; }
    ModelRow Button   { width: 8; height: 3; min-width: 6; margin-left: 1; }
    """

    def __init__(self, model: dict, installed: bool = False,
                 show_pull: bool = True, hw: dict | None = None, **kwargs) -> None:
        super().__init__(id=f"row-{_san(model['id'])}", **kwargs)
        self._model     = model
        self._installed = installed
        self._show_pull = show_pull
        self._hw        = hw or {}

    def compose(self) -> ComposeResult:
        m    = self._model
        safe = _san(m["id"])
        fit  = model_catalog.fit_rating(m, self._hw) if self._hw else None
        fit_text = _FIT_LABELS[fit][0] if fit in _FIT_LABELS else ""
        fit_cls  = f"mr-fit mr-fit-{fit or 'none'}"

        yield Label(m["id"],                                      classes="mr-id")
        yield Label(m.get("size", ""),                            classes="mr-size")
        yield Label(fit_text,                                     classes=fit_cls)
        yield Label(m.get("desc", ""),                            classes="mr-desc")
        yield Label("✓" if self._installed else " ",
                    id=f"chk-{safe}",                             classes="mr-chk")
        yield Button("Use",  id=f"use-{safe}",  variant="primary")
        if self._show_pull:
            yield Button("Pull", id=f"pull-{safe}")


class ModelBrowserScreen(Screen):
    BINDINGS = [("escape", "dismiss", "Close")]

    DEFAULT_CSS = """
    ModelBrowserScreen { background: #1A0A2E; }
    ModelBrowserScreen Header { background: #2D1B4E; color: #00B4FF; }
    ModelBrowserScreen Footer { background: #2D1B4E; color: #00FF88; }
    ModelBrowserScreen TabbedContent { height: 1fr; }
    ModelBrowserScreen TabPane       { padding: 0; }
    #search-bar { height: 3; padding: 0 2; background: #241540; }
    #search-bar Label { width: 10; color: #00FF88; content-align: left middle; }
    #search-bar Input { width: 1fr; }
    .tab-hint { color: #666699; height: 2; padding: 0 2; }
    .mb-empty { color: #555588; padding: 1 2; height: 3; }
    #pull-log { height: 8; background: #0A0518; border-top: solid #3A2260; }
    #btn-fetch-more { width: 100%; height: 3; margin: 0; }
    """

    def __init__(self, project_slug: str, local_endpoint: str,
                 hw: dict | None = None) -> None:
        super().__init__()
        self._slug              = project_slug
        self._endpoint          = local_endpoint.rstrip("/")
        self._hw                = hw or {}
        self._installed: set[str] = set()
        self._extra_models: list[dict] = []
        self._catalog_lock      = asyncio.Lock()

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="search-bar"):
            yield Label("Search:")
            yield Input(placeholder="name, tag, or description…", id="model-search")
        with TabbedContent("Installed", "Catalog"):
            with TabPane("Installed", id="tab-installed"):
                yield Label("Models available at your local endpoint.", classes="tab-hint")
                yield ScrollableContainer(id="installed-list")
            with TabPane("Catalog", id="tab-catalog"):
                yield Label("Popular Ollama models — Pull to download, Use to activate.",
                            classes="tab-hint")
                yield ScrollableContainer(id="catalog-list")
                yield Button("⬇ Fetch more from Ollama…", id="btn-fetch-more")
        yield Log(id="pull-log", auto_scroll=True)
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._fetch_installed())

    # ── Catalog helpers ───────────────────────────────────────────────────────

    def _all_catalog(self) -> list[dict]:
        seen = {m["id"] for m in model_catalog.CATALOG}
        extra = [m for m in self._extra_models if m["id"] not in seen]
        return model_catalog.CATALOG + extra

    def _search_catalog(self, query: str) -> list[dict]:
        if not query:
            return self._all_catalog()
        q = query.lower()
        return [
            m for m in self._all_catalog()
            if q in m["id"].lower()
            or q in m.get("display", m["id"]).lower()
            or q in m.get("desc", "").lower()
            or any(q in t for t in m.get("tags", []))
        ]

    # ── List builders ─────────────────────────────────────────────────────────

    async def _rebuild_catalog(
        self, models: list[dict], installed: frozenset | None = None
    ) -> None:
        if installed is None:
            installed = frozenset(self._installed)
        async with self._catalog_lock:
            await self._do_rebuild_catalog(models, installed)

    async def _do_rebuild_catalog(
        self, models: list[dict], installed: frozenset
    ) -> None:
        try:
            container = self.query_one("#catalog-list", ScrollableContainer)
        except Exception:
            return  # screen dismissed
        await container.remove_children()
        if not models:
            await container.mount(Label("No models match.", classes="mb-empty"))
            return
        hw = self._hw
        models_sorted = sorted(
            models,
            key=lambda m: _FIT_ORDER.get(model_catalog.fit_rating(m, hw), 4),
        )
        for m in models_sorted:
            await container.mount(
                ModelRow(m, installed=m["id"] in installed, show_pull=True, hw=self._hw)
            )

    async def _rebuild_installed(self) -> None:
        container = self.query_one("#installed-list", ScrollableContainer)
        await container.remove_children()
        if not self._installed:
            await container.mount(
                Label("No models found. Is Ollama running?", classes="mb-empty")
            )
            return
        for mid in sorted(self._installed):
            entry = model_catalog.get_by_id(mid) or {
                "id": mid, "display": mid, "size": "", "tags": [], "desc": "(not in catalog)",
            }
            await container.mount(ModelRow(entry, installed=True, show_pull=False, hw=self._hw))

    # ── Fetch installed ───────────────────────────────────────────────────────

    async def _fetch_installed(self) -> None:
        try:
            pull_log = self.query_one("#pull-log", Log)
        except Exception:
            return  # screen dismissed
        pull_log.write_line(f"$ GET {self._endpoint}/v1/models")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self._endpoint}/v1/models")
            if resp.status_code == 200:
                self._installed = {item["id"] for item in resp.json().get("data", [])}
                pull_log.write_line(f"✓ {len(self._installed)} model(s) found")
            else:
                pull_log.write_line(f"✗ HTTP {resp.status_code}")
        except httpx.ConnectError:
            pull_log.write_line(f"✗ Cannot connect to {self._endpoint}")
        except Exception as exc:
            log.exception("Fetch installed failed")
            pull_log.write_line(f"✗ {exc}")
        await self._rebuild_installed()
        snapshot = frozenset(self._installed)
        try:
            query = self.query_one("#model-search", Input).value.strip()
        except Exception:
            return
        await self._rebuild_catalog(self._search_catalog(query), snapshot)

    # ── Fetch more from Ollama ────────────────────────────────────────────────

    async def _fetch_more_from_ollama(self) -> None:
        import re as _re
        import html as _html
        try:
            pull_log = self.query_one("#pull-log", Log)
        except Exception:
            return
        pull_log.write_line("$ Fetching model list from ollama.com/library…")
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                resp = await client.get("https://ollama.com/library")
            if resp.status_code != 200:
                pull_log.write_line(f"✗ HTTP {resp.status_code}")
                self.app.notify("Could not reach ollama.com.", severity="warning")
                return
            html_text = resp.text
            # Parse model blocks — each has x-test-model-title title="<name>"
            existing_ids = {m["id"] for m in self._all_catalog()}
            new_models: list[dict] = []
            for match in _re.finditer(r'x-test-model-title[^>]+title="([^"]+)"', html_text):
                mid = match.group(1).strip()
                if not mid or mid in existing_ids:
                    continue
                chunk = html_text[match.start(): match.start() + 1000]
                desc_m = _re.search(r'<p[^>]*>(.*?)</p>', chunk, _re.DOTALL)
                desc = _html.unescape(
                    _re.sub(r'<[^>]+>', '', desc_m.group(1)).strip()
                ) if desc_m else ""
                new_models.append({
                    "id": mid,
                    "display": mid,
                    "size": "",
                    "vram_min_gb": 0.0,
                    "tags": [],
                    "desc": desc[:120],
                })
                existing_ids.add(mid)  # prevent duplicates within this batch
            self._extra_models.extend(new_models)
            pull_log.write_line(f"✓ {len(new_models)} additional model(s) loaded")
            self.app.notify(f"{len(new_models)} new models added to catalog.", severity="information")
        except httpx.ConnectError:
            pull_log.write_line("✗ Cannot connect to ollama.com — check internet connection")
            self.app.notify("Cannot reach ollama.com.", severity="warning")
            return
        except Exception as exc:
            log.exception("Failed to fetch Ollama library")
            pull_log.write_line(f"✗ {exc}")
            return
        try:
            query = self.query_one("#model-search", Input).value.strip()
        except Exception:
            return
        snapshot = frozenset(self._installed)
        await self._rebuild_catalog(self._search_catalog(query), snapshot)

    # ── Pull ──────────────────────────────────────────────────────────────────

    async def _pull_model(self, model_id: str) -> None:
        try:
            pull_log = self.query_one("#pull-log", Log)
        except Exception:
            return  # screen dismissed
        try:
            pull_log.write_line(f"\n$ ollama pull {model_id}")
        except Exception:
            return
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "pull", model_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            if proc.stdout is None:
                try:
                    pull_log.write_line("✗ ollama pull: stdout unavailable")
                except Exception:
                    pass
                return
            async for raw in proc.stdout:
                try:
                    pull_log.write_line(raw.decode(errors="replace").rstrip())
                except Exception:
                    break  # screen dismissed mid-stream
            await proc.wait()
            if proc.returncode == 0:
                try:
                    pull_log.write_line(f"✓ {model_id} pulled.")
                except Exception:
                    pass
                self.app.notify(f"'{model_id}' pulled.", severity="information")
                await self._fetch_installed()
            else:
                try:
                    pull_log.write_line(f"✗ Exit {proc.returncode}")
                except Exception:
                    pass
                self.app.notify(f"Pull failed for '{model_id}'.", severity="error")
        except FileNotFoundError:
            try:
                pull_log.write_line("✗ 'ollama' not found on PATH.")
            except Exception:
                pass
            self.app.notify("ollama is not installed or not on PATH.", severity="error")
        except Exception:
            log.exception("Pull failed: %s", model_id)
            try:
                pull_log.write_line("✗ Unexpected error — see log.")
            except Exception:
                pass
        finally:
            if proc is not None and proc.returncode is None:
                try:
                    await proc.wait()
                except Exception:
                    pass

    # ── Use / select ──────────────────────────────────────────────────────────

    def _use_model(self, model_id: str) -> None:
        from nexus.core.config_manager import load_project_config, save_project_config
        try:
            cfg = load_project_config(self._slug)
            cfg.setdefault("localai", {})
            cfg["localai"]["model"]       = model_id
            cfg["localai"]["run_command"] = f'ollama run {model_id} "$NEXUS_PROMPT"'
            save_project_config(self._slug, cfg)
            self.app.notify(f"Model set to '{model_id}'.", severity="information")
        except Exception:
            log.exception("Failed to save model selection")
            self.app.notify("Failed to save — see log.", severity="error")
            return
        self.dismiss(model_id)

    # ── Button handler ────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        try:
            if bid == "btn-fetch-more":
                self.run_worker(self._fetch_more_from_ollama())
            elif bid.startswith("use-"):
                model_id = self._model_id_from_bid(bid, "use-")
                if model_id:
                    self._use_model(model_id)
            elif bid.startswith("pull-"):
                model_id = self._model_id_from_bid(bid, "pull-")
                if model_id:
                    self.run_worker(self._pull_model(model_id))
        except Exception:
            log.exception("Button error: %s", bid)

    def _model_id_from_bid(self, bid: str, prefix: str) -> str | None:
        safe = bid[len(prefix):]
        try:
            return self.query_one(f"#row-{safe}", ModelRow)._model["id"]
        except Exception:
            pass
        for entry in model_catalog.CATALOG:
            if _san(entry["id"]) == safe:
                return entry["id"]
        for mid in self._installed:
            if _san(mid) == safe:
                return mid
        return None

    # ── Search ────────────────────────────────────────────────────────────────

    def _do_search(self, query: str) -> None:
        if query:
            try:
                self.query_one(TabbedContent).active = "tab-catalog"
            except Exception:
                pass
        snapshot = frozenset(self._installed)
        self.run_worker(
            self._rebuild_catalog(self._search_catalog(query), snapshot),
            exclusive=True,
            group="catalog-rebuild",
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "model-search":
            self._do_search(event.value.strip())

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "model-search":
            self._do_search(event.value.strip())
