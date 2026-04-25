# /review — Multi-agent codebase review

Run a parallel multi-agent sweep of the Nexus codebase, synthesize the findings, and
write a prioritized improvement plan to a new plan file.

## Workflow

### Step 1 — Parallel exploration (spawn all 5 agents in ONE message)

Launch these 5 Explore agents simultaneously, each with "very thorough" search breadth:

**Agent A — Core & AI layer**
Scope: `nexus/core/`, `nexus/ai/`, `nexus/app.py`
Look for: incorrect error handling in async paths; skills registered with wrong scope or
missing required fields; config keys read with no default that could KeyError; circular
import risks; any place `is_ai_configured()` is bypassed; MCPClient lifetime issues.

**Agent B — UI base & shared widgets**
Scope: `nexus/ui/` (all files including `base_project_screen.py`, `chat_panel.py`,
`tiles.py`, `settings_screen.py`, `add_project_screen.py`, `mcp_screen.py`)
Look for: Textual widget IDs that clash across screens; CSS rules that reference IDs
present in multiple screens (causing cross-screen bleed); `query_one` calls that could
raise `NoMatches` if a widget is hidden or not yet mounted; event propagation bugs
(missing `event.stop()`); workers started on already-dismissed screens.

**Agent C — Module screens A**
Scope: `modules/git/`, `modules/localai/`, `modules/custom/`, `modules/web/`,
`modules/research/`, `modules/codex/`
Look for: subprocess calls where user-controlled data could reach the shell; missing
`FileNotFoundError` guards around Path reads; `_populate_content` methods that don't
clear the content area before adding new widgets (causing duplication on refresh);
skill handlers that don't match the registered schema; config keys accessed without
`.get()` default.

**Agent D — Module screens B**
Scope: `modules/journal/`, `modules/game/`, `modules/org/`, `modules/home/`,
`modules/streaming/`, `modules/vtube/`
Same checks as Agent C. Also: blocking file I/O called from the UI thread (not wrapped
in `run_in_executor`); `open_path()` used correctly (not hard-coded `xdg-open`);
`check_binary()` used at save time for all modules that need an external binary.

**Agent E — Module screens C + all skills**
Scope: `modules/emulator/`, `modules/vault/`, `modules/server/`, `modules/backup/`,
all `modules/*/skills.py`
Same checks as Agent C. Also: skill handlers that do blocking I/O without
`run_in_executor`; skills whose `schema["required"]` list doesn't match what the handler
actually reads from `args`; `backup_ops.py` path expansion consistency; server module
`docker`/`systemctl` commands built with user-supplied strings.

Each agent must report findings as:
```
FILE:LINE — [P1/P2/P3] short description
```
P1 = bug/data-loss/security, P2 = broken feature, P3 = inconsistency/missing coverage.
Omit anything that is a style preference or already documented as a known limitation.

---

### Step 2 — Synthesize (do this yourself, no extra agent needed)

After all 5 agents return:

1. Collect every finding into a flat list.
2. Deduplicate: if two agents flag the same file+line, keep the higher-priority rating
   and note "flagged by N agents".
3. Identify systemic patterns: if 3+ findings share a root cause (e.g. "missing
   run_in_executor for blocking calls"), group them under one systemic heading.
4. Sort: P1 first, then P2, then P3. Within each tier, systemic issues before one-offs.
5. Trim P3 one-offs if the total list exceeds 25 items — keep systemic P3s.

---

### Step 3 — Write plan file

Write the findings to a new file at `/home/constantin/.claude/plans/` with a short
descriptive slug (e.g. `review-2026-04-25.md`). Format:

```markdown
# Review — <date>

## Context
Multi-agent sweep of the Nexus codebase. N findings across M files.
Systemic issues: <list themes>.

## P1 — Bugs / Security
...

## P2 — Broken behaviour
...

## P3 — Inconsistencies / Missing coverage
(systemic only if list is long)

## Systemic patterns
...
```

Include file:line for every item. Do NOT include vague recommendations without a
specific location. After writing the file, tell the user the path and a one-sentence
summary of the most critical finding.
