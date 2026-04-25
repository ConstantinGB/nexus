from __future__ import annotations
import re
from datetime import date
from pathlib import Path

from textual.widgets import Label, Button, Log
from textual.containers import Vertical, Horizontal

from nexus.core.logger import get
from nexus.core.platform import open_path
from nexus.ui.base_project_screen import BaseProjectScreen, InputModal, _screen_css

log = get("org.project_screen")

_PLAN_TEMPLATE = """\
# {title}

## Goals

- [ ]

## Tasks

- [ ]

## Notes

"""

_DIAGRAM_TEMPLATE = """\
# {title}

```mermaid
flowchart LR
    A[Start] --> B[Step 1]
    B --> C[End]
```
"""

_SCHEDULE_TEMPLATE = """\
# Weekly Schedule

| Time  | Monday | Tuesday | Wednesday | Thursday | Friday |
|-------|--------|---------|-----------|----------|--------|
| 09:00 |        |         |           |          |        |
| 10:00 |        |         |           |          |        |
| 11:00 |        |         |           |          |        |
| 12:00 |        |         |           |          |        |
| 13:00 |        |         |           |          |        |
| 14:00 |        |         |           |          |        |
| 15:00 |        |         |           |          |        |
| 16:00 |        |         |           |          |        |
| 17:00 |        |         |           |          |        |
"""


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "plan"


class OrgProjectScreen(BaseProjectScreen):
    MODULE_KEY   = "org"
    MODULE_LABEL = "ORG"
    SETUP_FIELDS = [
        {"id": "output_dir", "label": "Plans / output directory",
         "placeholder": "~/org"},
    ]

    DEFAULT_CSS = _screen_css("OrgProjectScreen")

    # ── Action buttons ────────────────────────────────────────────────────────

    def _compose_action_buttons(self) -> list:
        return [
            Button("New Plan",     id="btn-new-plan",     variant="primary"),
            Button("New Diagram",  id="btn-new-diagram"),
            Button("New Schedule", id="btn-new-schedule"),
            Button("Open Dir",     id="btn-open-dir"),
            Button("Refresh",      id="btn-refresh"),
        ]

    # ── Main content ──────────────────────────────────────────────────────────

    async def _populate_content(self) -> None:
        area = self.query_one("#content-area", Vertical)
        await area.remove_children()

        output_dir = Path(self._mod.get("output_dir", "")).expanduser()
        widgets: list = [
            Horizontal(
                Label("Output dir:", classes="info-key"),
                Label(str(output_dir), classes="info-val"),
                classes="info-row",
            ),
        ]

        if output_dir.exists():
            files = sorted(output_dir.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            widgets.append(
                Horizontal(
                    Label("Files:", classes="info-key"),
                    Label(str(len(files)), classes="info-val"),
                    classes="info-row",
                )
            )
            widgets.append(Label("Recent files:", classes="section-label"))
            for f in files[:20]:
                try:
                    text = f.read_text(errors="replace")
                    done  = text.count("[x]") + text.count("[X]")
                    total = done + text.count("[ ]")
                    pct   = f"  {done}/{total} done" if total else ""
                except Exception:
                    pct = ""
                widgets.append(
                    Label(f"  {f.name}{pct}", classes="hint")
                )
        else:
            widgets.append(Label("Directory not found — it will be created on first use.", classes="hint"))

        await area.mount(*widgets)

    # ── Button handler ────────────────────────────────────────────────────────

    def _handle_action(self, bid: str | None) -> None:
        output_dir = Path(self._mod.get("output_dir", "")).expanduser()

        if bid == "btn-new-plan":
            self.app.push_screen(
                InputModal("New Plan", "Plan name:", "my-plan"),
                lambda name: self._create_file(name, output_dir, _PLAN_TEMPLATE, "plan"),
            )
        elif bid == "btn-new-diagram":
            self.app.push_screen(
                InputModal("New Diagram", "Diagram name:", "my-diagram"),
                lambda name: self._create_file(name, output_dir, _DIAGRAM_TEMPLATE, "diagram"),
            )
        elif bid == "btn-new-schedule":
            today = date.today().isoformat()
            self._create_file(f"schedule-{today}", output_dir, _SCHEDULE_TEMPLATE, "schedule")
        elif bid == "btn-open-dir":
            self.run_worker(self._run_cmd(open_path(output_dir)))
        elif bid == "btn-refresh":
            self.run_worker(self._populate_content())

    def _create_file(
        self,
        name: str | None,
        output_dir: Path,
        template: str,
        kind: str,
    ) -> None:
        if not name:
            return
        slug = _slugify(name)
        dest = output_dir / f"{slug}.md"
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                dest.write_text(template.format(title=name))
            self.app.notify(f"{kind.capitalize()} created: {dest.name}")
            self.run_worker(self._populate_content())
        except Exception:
            log.exception("Failed to create %s: %s", kind, dest)
            self.app.notify(f"Could not create {kind} — see log.", severity="error")
