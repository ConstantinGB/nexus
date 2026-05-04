---
description: Textual TUI patterns, async worker guards, and robustness rules for all TUI screens
paths:
  - "nexus/ui/tui/**"
  - "nexus/ui/*.py"
  - "modules/*/project_screen.py"
  - "modules/*/setup_screen.py"
---

## Textual UI Patterns

- **Multi-step forms**: use `_ALL_STEPS` list + `_show(step_id)` toggling `.display` on each container. Do NOT use `ContentSwitcher` — it has CSS height issues.
- **Async workers**: pass the coroutine directly — `self.run_worker(self._my_async_method())`, not a lambda or method reference.
- **Blocking calls**: `asyncio.get_event_loop().run_in_executor(None, blocking_fn, args)`.
- **Modal screens**: `self.app.push_screen(Modal(...), callback)` — `push_screen` is on `App`, not `Screen`.
- **Button events in tiles**: call `event.stop()` in `on_button_pressed` to prevent the event from bubbling to `on_click` on the parent.
- **Dynamic grid sizing**: set `widget.styles.height = rows * tile_height` in `on_mount` when a grid must fit all items without scrolling.
- **Custom messages**: subclass `Message` inside the widget class, post with `self.post_message(...)`, receive with `on_<widget_class>_<message_class>` naming.

## BaseProjectScreen Contract

Subclass in `modules/<id>/project_screen.py`. Required class attributes:

- `MODULE_KEY` — config dict key (e.g. `"git"`)
- `MODULE_LABEL` — human label for the top bar
- `SETUP_FIELDS` — list of `(key, label, placeholder)` tuples; rendered as inline setup form
- `REQUIRED_BINARIES` — list of `(binary, display_name)` checked on mount; missing → `MissingDepsModal`

Required methods: `_compose_action_buttons()`, `_populate_content()`, `_handle_action(action_id)`.

`_run_cmd(cmd, ...)` is the canonical async helper — use it for all subprocess calls; it applies the worker-after-dismiss guard automatically.

## Robustness Patterns

### Worker-after-dismiss guard

`run_worker()` workers outlive the screen that launched them. Every `query_one()` inside an async worker must be wrapped:

```python
async def _my_worker(self) -> None:
    try:
        ui_log = self.query_one("#output-log", Log)
    except Exception:
        return  # screen dismissed
    async for line in stream:
        try:
            ui_log.write_line(line)
        except Exception:
            break  # screen dismissed mid-stream
```

`BaseProjectScreen._run_cmd` already applies this — it is the canonical implementation.

### Explicit stdout check

`assert proc.stdout` is silently disabled under `python -O`. Always use:

```python
proc = await asyncio.create_subprocess_exec(...)
if proc.stdout is None:
    log.error("stdout unavailable for %s", cmd)
    return
async for raw in proc.stdout:
    ...
```

### asyncio.Event for shared ready flags

Use `asyncio.Event` — a plain `bool` can be read stale by a concurrent coroutine:

```python
self._server_ready = asyncio.Event()
self._server_ready.set()    # signal ready
self._server_ready.clear()  # signal stopped
if not self._server_ready.is_set(): ...
```

### Frozen snapshot for concurrent set reads

When a mutable set is reassigned by one worker while another iterates it, snapshot it before spawning:

```python
snapshot = frozenset(self._installed)
self.run_worker(self._rebuild_catalog(models, snapshot))
```

### Docker container lifecycle

`NexusApp._docker_containers: set[str]` tracks all open containers. Screens register on `on_mount`, deregister on `on_dismiss`. `NexusApp.on_unmount` calls `subprocess.run(["docker", "stop", "--time=5", name])` synchronously (blocking is correct — asyncio loop may already be shutting down).

`docker_ops.stop_container` ignores "No such container" errors — idempotent.
