# Tab System Overhaul

## Status: PLANNED

---

## Root Cause Analysis

The tab bar is a widget (`ProjectTabBar`) yielded inside each project screen's `compose()`.
Four modules — **git, localai, sdforge, custom** — do NOT inherit from `BaseProjectScreen`
and have their own `compose()` that never yields `ProjectTabBar`. They also have their own
`action_dismiss()` that never calls `close_project_tab()`. This causes all three reported symptoms:

- **Module takes over, no tabs visible** — git/localai/sdforge/custom `compose()` missing `yield ProjectTabBar()`
- **More tabs than expected** — same 4 screens' `action_dismiss` never calls `close_project_tab()` on Escape
- **"+" barely visible** — CSS `background: transparent` on `.tab-add-btn`
- **Terminal leak on tab switch** — `switch_to_tab` wraps terminal stop in `isinstance(..., BaseProjectScreen)` guard

There are no architectural changes needed — the per-screen tab bar approach is correct.
Every bug is a missing line or wrong CSS value.

---

## Changes

### 1. `nexus/ui/project_tabs.py` — Fix "+" button visibility

`.tab-add-btn` CSS:
- Change `background: transparent` → `background: #1A0A2E`
- Add `border: solid #3A2260` so it visually matches the other tab buttons

### 2. `nexus/app.py` — `switch_to_tab`: stop terminals on any screen type

Remove the `isinstance(current, BaseProjectScreen)` guard so terminal stop is attempted
on all screen types:

```python
current = self.screen
for tid in ("#claude-terminal", "#bash-terminal"):
    try:
        from nexus.ui.terminal_widget import Terminal
        current.query_one(tid, Terminal).stop()
    except Exception:
        pass
```

### 3. `modules/git/project_screen.py`

**compose()** — after `yield Header()` add:
```python
from nexus.ui.project_tabs import ProjectTabBar
yield ProjectTabBar()
```

**action_dismiss()** (line 835) — before `self.dismiss(result)` add:
```python
if hasattr(self.app, "close_project_tab"):
    self.app.close_project_tab(self.project.slug)
```

### 4. `modules/localai/project_screen.py`

Same two changes as git (compose + action_dismiss at line 194).

### 5. `modules/sdforge/project_screen.py`

**compose()** (line 211) — same ProjectTabBar addition after `yield Header()`.

**action_dismiss** — Two issues:
- Line 295 is dead code (Python sees the second definition at line 649, which overrides it). Remove line 295.
- Line 649 `action_dismiss`: in the `else` branch, before `super().action_dismiss(result)` add the `close_project_tab` call. Also add it before `_stop_and_dismiss` starts (tab should be closed when server stops).

The updated line 649 block:
```python
def action_dismiss(self, result=None) -> None:
    if hasattr(self.app, "close_project_tab"):
        self.app.close_project_tab(self.project.slug)
    if self._proc and self._proc.returncode is None:
        self.run_worker(self._stop_and_dismiss(result))
    else:
        super().action_dismiss(result)
```

(`_stop_and_dismiss` calls `self.app.pop_screen()` directly — close_project_tab must run
before that, not inside the async worker.)

### 6. `modules/custom/project_screen.py`

Same two changes: ProjectTabBar in compose() + close_project_tab in action_dismiss() (line 206).

---

## What is NOT changing

- No changes to `BaseProjectScreen` or any of the 15+ modules that already inherit from it.
- No changes to the tab switching logic (`switch_to_tab`, `open_project_tab`) beyond the terminal fix in #2.
- `_going_home_for_new_tab` flag is kept as-is (harmless; guards BaseProjectScreen's action_dismiss).

---

## Verification

1. Open a **git** project → tab bar visible at top, "+" clearly visible.
2. Open a second project via "+" → both tabs shown; clicking between them switches screens correctly.
3. Press Escape on any project → tab removed from the bar; back to home with no stale tabs.
4. Ctrl+Tab cycles tabs.
5. Repeat all steps with **localai**, **sdforge**, **custom** modules.
