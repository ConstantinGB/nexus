# Agent Architecture Adaptation Plan for Nexus

## Preface

This plan synthesises four concept papers on local, resource-efficient AI agent architectures
with a deep reading of the Nexus codebase. The goal is not to rewrite Nexus — the existing
design is solid — but to identify the specific gaps where the paper's principles, applied
selectively, would most improve reliability, capability, and local-AI usefulness.

The papers describe an idealised five-layer pipeline:

```text
Input Router → Planner → Argument Generator → Validator → Tool Executor → Responder
```

Nexus currently has most of these roles collapsed into a single monolithic `AIClient.chat()`
loop. The plan below is organised as a series of focused additions, each self-contained and
independently deployable.

---

## Part 1 — Current State Analysis

### What exists and works well

- `AIClient` cleanly abstracts Claude API vs. local (OpenAI-compatible) behind one interface.
- `SkillRegistry` is a proper tool catalog with scope filtering: modules expose only their
  own skills, global skills are always present.
- `MCPClient` adds external tool capability without changing the core loop.
- Mycelium is a clean inter-module event bus with typed `Flow` objects and async handlers.
- The five existing Mycelium flows (git→journal, research→codex, etc.) are well-structured
  and already use a "deterministic executor + AI synthesiser" pattern internally.
- Operator module is the most capable sub-agent: 9 skills, three data layers, full GUI.

### What is missing vs. the ideal architecture

| Paper Layer | Nexus status | Gap |
| ----------- | ------------ | ---- |
| Intent Router | None | Every message hits the LLM with all tools unconditionally |
| Tool scope narrowing | Coarse (by module key only) | No intra-module relevance filtering |
| Argument validation | None pre-execution | Schema exists but is not checked before `handler(args)` |
| Retry on invalid output | None | Validation failures surface as runtime exceptions, not structured retries |
| Local AI reliability | Minimal | Graceful degradation drops tools; no structured-output enforcement |
| Embedding-based retrieval | None | Research/Codex notes are not semantically searchable |
| Typed inter-agent contracts | Informal | Mycelium payloads are untyped dicts; flows have no status model |
| Sub-agent specialisation | Partial | Operator is a capable sub-agent but has no formal API surface |

### Which gaps matter most

**Immediate high impact:** Argument validation and retry — protects tool execution from bad
model output at near-zero cost.

**High impact for local AI:** Structured output enforcement and intent-aware tool narrowing —
local 7B models fail mainly because they receive too many tools and too little output guidance.

**Medium impact:** Typed Mycelium contracts and flow status — makes cross-module automation
more debuggable and extensible.

**Longer term:** Embedding-based memory — enables semantic retrieval across notes, making
Research, Codex, and Operator dramatically more capable.

---

## Part 2 — Architecture Mapping

The papers' five layers map to Nexus as follows:

```text
[Paper Layer]           [Nexus Component]                    [Status]
─────────────────────────────────────────────────────────────────────
Input Router          → nexus/ai/intent_router.py            TO BUILD
Planner               → AIClient._chat_anthropic/local()     EXISTS (monolithic)
Argument Generator    → model tool_use response              EXISTS (unvalidated)
Validator             → nexus/ai/validator.py                TO BUILD
Tool Executor         → SkillRegistry.call()                 EXISTS (no pre-check)
Responder             → text extraction in AIClient          EXISTS (adequate)
Sub-agents            → Mycelium + per-module skills         EXISTS (informal)
Memory                → nexus/ai/memory.py                   TO BUILD
```

**Design principle for Nexus:** Claude API is a strong enough model that it does not need a
separate Planner/Argument Generator split — it handles both reliably in one pass. Local models
(Ollama, LM Studio) *do* benefit from that split because they are weaker at schema compliance.
The architecture should therefore be **dual-track**: Claude path runs the current loop with
validation added; Local path runs a more structured, constrained flow.

---

## Part 3 — Implementation Roadmap

### Phase 1 — Pre-Execution Argument Validation

**Files:** `nexus/ai/validator.py` (new), `nexus/ai/skill_registry.py` (modified), `nexus/ai/client.py` (modified)

#### 1A. Create `nexus/ai/validator.py`

```python
"""JSON schema validation for skill arguments before execution."""
import jsonschema

class ValidationError(Exception):
    def __init__(self, tool_name: str, errors: list[str]):
        self.tool_name = tool_name
        self.errors    = errors
        super().__init__(f"{tool_name}: {'; '.join(errors)}")

def validate_args(name: str, args: dict, schema: dict) -> None:
    """Raise ValidationError if args do not conform to schema."""
    try:
        jsonschema.validate(instance=args, schema=schema)
    except jsonschema.ValidationError as exc:
        raise ValidationError(name, [exc.message]) from exc
```

The `jsonschema` package is already a common Python dependency; add it to `pyproject.toml`
if not already present.

#### 1B. Integrate into `SkillRegistry.call()`

Current `call()` calls the handler directly. Add schema validation before execution:

```python
async def call(self, name: str, args: dict) -> str:
    tool = self._tools.get(name)
    if tool is None:
        return json.dumps({"error": f"Unknown skill: {name}"})
    try:
        validate_args(name, args, tool["schema"])   # NEW
        return await tool["handler"](args)
    except ValidationError as exc:
        log.warning("Skill %s arg validation failed: %s", name, exc.errors)
        return json.dumps({"validation_error": exc.errors, "tool": name})
    except Exception as exc:
        log.exception("Skill %s raised an exception", name)
        return json.dumps({"error": str(exc)})
```

**Why this matters:** The model occasionally mis-types arguments (string where int expected,
missing required field). Currently this causes an opaque exception that the model cannot
use to self-correct. Returning a structured `validation_error` gives the next iteration of
the tool loop explicit feedback to retry with correct arguments.

#### 1C. Structured retry in `AIClient`

In `_chat_anthropic()` and `_chat_local()`, when a tool result contains `"validation_error"`,
inject a correction hint into the next iteration's tool_result content rather than the raw
error:

```python
if "validation_error" in result_dict:
    tool_content = (
        f"Your arguments for {name} were invalid: {result_dict['validation_error']}. "
        f"The schema requires: {tool['schema']}. Please retry with valid arguments."
    )
```

This closes the retry loop: the model sees the schema, knows what went wrong, and corrects.

---

### Phase 2 — Intent-Aware Tool Narrowing

**Files:** `nexus/ai/intent_router.py` (new), `nexus/ui/gui/chat_panel.py` (modified),
`nexus/ui/tui/base_project_screen.py` (modified)

#### 2A. Create `nexus/ai/intent_router.py`

The intent router is **deliberately simple** — rule-based keyword matching is sufficient
and has zero latency. No classifier model needed in Phase 2.

```python
"""Lightweight intent classification for skill scope narrowing."""

# Intra-module keyword maps: module → keyword signals
_SCOPE_HINTS: dict[str, list[str]] = {
    "calendar":  ["event", "meeting", "appointment", "schedule", "calendar", "remind", "today", "tomorrow"],
    "notes":     ["note", "write", "draft", "document", "record", "memo"],
    "todo":      ["task", "todo", "do", "complete", "finish", "deadline", "priority"],
    "git":       ["commit", "push", "pull", "branch", "repo", "diff", "stash"],
    "research":  ["research", "paper", "find", "search", "analyse", "literature"],
    "codex":     ["codex", "knowledge", "zettelkasten", "entry", "concept", "idea"],
    "journal":   ["journal", "diary", "reflection", "log", "write about"],
    "org":       ["plan", "project", "roadmap", "outline", "org", "strategy"],
    "backup":    ["backup", "snapshot", "restore", "restic"],
    "vault":     ["encrypt", "decrypt", "key", "gpg", "vault", "password", "secret"],
    "security":  ["firewall", "vpn", "audit", "nmap", "ports", "fail2ban"],
    "localai":   ["ollama", "local model", "inference", "generate", "image", "stable diffusion"],
    "promptopt": ["prompt", "optimize", "improve", "rewrite prompt"],
}

_TOOL_TRIGGER_WORDS = {
    "create", "add", "new", "make", "insert",
    "delete", "remove", "clear",
    "update", "edit", "change", "set",
    "list", "show", "get", "find", "search", "fetch",
    "run", "execute", "start", "stop", "launch",
    "backup", "restore", "sync",
}


def classify(text: str, active_module: str) -> dict:
    """
    Returns:
        {
            "likely_tool_use": bool,        # does the message likely need a tool?
            "intra_scope_hints": list[str], # sub-scopes within the active module
            "complexity": "simple"|"moderate"|"complex",
        }
    """
    lower = text.lower()
    words = set(lower.split())

    likely_tool = bool(words & _TOOL_TRIGGER_WORDS) or "?" not in text
    intra_hints = [
        scope for scope, keywords in _SCOPE_HINTS.items()
        if any(kw in lower for kw in keywords)
    ]
    # Complexity heuristic: word count + conjunction count
    word_count = len(text.split())
    conjunctions = sum(lower.count(w) for w in (" and ", " then ", " also ", " after "))
    if word_count < 8 and conjunctions == 0:
        complexity = "simple"
    elif word_count > 40 or conjunctions >= 2:
        complexity = "complex"
    else:
        complexity = "moderate"

    return {
        "likely_tool_use": likely_tool,
        "intra_scope_hints": intra_hints,
        "complexity": complexity,
    }
```

#### 2B. Apply in `AIClient.chat()`

Accept an optional `intent: dict | None = None` parameter. When `likely_tool_use=False`,
do not pass tools to the model — answer directly. This removes tool overhead for
conversational messages.

When `intra_scope_hints` are present and the active module is "operator", further filter
the skill list to only the relevant sub-skill group (calendar | notes | todo). This cuts
the tool list from 9 operator skills to ~3 per interaction.

#### 2C. Apply in `ChatPanel` and `BaseProjectScreen`

Before calling `AIClient.chat()`, call `intent_router.classify(text, active_module)`.
Pass the `intent` dict to `chat()`. This is a one-line addition to the send path.

**Impact on local AI:** A 7B model receiving 3 relevant tools reliably outperforms the same
model receiving 15+ tools, even without any model upgrade. This is the single highest-leverage
change for local AI reliability.

---

### Phase 3 — Local AI Reliability Layer

**Files:** `nexus/ai/client.py` (modified)

#### 3A. Structured output system prompt injection

When `self._provider == "local"`, prepend a strong structured output directive to the
system prompt:

```python
_LOCAL_TOOL_PREFIX = (
    "You are a precise assistant. When using tools, you MUST respond with valid JSON "
    "matching the exact schema provided. Do not add explanation before or after the "
    "JSON tool call. If you cannot use a tool, respond with plain text only.\n\n"
)
```

Prepend this to `system_prompt` in `_chat_local()`.

#### 3B. Single-tool-at-a-time mode for local models

Local models often produce malformed multi-tool calls. Optionally limit to one tool call
per iteration with explicit re-prompting:

Add `max_tools_per_turn: int = 1` (for local) vs. unlimited (for Claude). After processing
the first tool result, send back the result before processing more. This serialises tool
use but dramatically improves per-step reliability.

#### 3C. Structured retry with countdown

Current local retry: one retry without tools. Extend to:

1. First failure: retry with explicit schema reminder
2. Second failure: retry with single allowed tool (the one the model tried to use)
3. Third failure: drop tools, return plain response

This "narrowing fallback" gives local models multiple recovery paths.

#### 3D. Local model JSON repair

Add `_repair_json(text: str) -> str | None` that tries `json.loads()`, then strips
common local model cruft (markdown fences, preamble text before `{`, trailing prose)
before giving up. Applied to tool argument parsing in `_chat_local()`.

```python
def _repair_json(text: str) -> str | None:
    text = text.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    # Find first { ... } block
    m = re.search(r'\{.*\}', text, re.DOTALL)
    if m:
        try:
            json.loads(m.group(0))
            return m.group(0)
        except json.JSONDecodeError:
            pass
    return None
```

---

### Phase 4 — Enhanced Mycelium: Typed Contracts and Flow Status

**Files:** `nexus/core/mycelium.py` (modified), `nexus/ai/flow_handlers.py` (modified)

#### 4A. Typed `FlowPayload` and `FlowResult`

Replace the current untyped `dict` payloads with dataclasses:

```python
@dataclass
class FlowPayload:
    source_slug: str | None = None
    target_slug: str | None = None
    content:     str | None = None   # primary text payload
    metadata:    dict = field(default_factory=dict)

@dataclass
class FlowResult:
    success:    bool
    action:     str
    output_path: str | None = None
    summary:    str | None = None
    error:      str | None = None
```

This gives flow handlers a stable, self-documenting interface. The `run_flow` skill and
`bus.send()` are updated to accept/return these types (serialised as JSON for backward
compatibility with string-based callers).

#### 4B. Flow status tracking via Mycelium

Add to `Mycelium`:

```python
self._running_flows: dict[str, FlowResult] = {}   # action → latest result

def flow_status(self, action: str) -> FlowResult | None:
    return self._running_flows.get(action)

def all_flow_statuses(self) -> dict[str, FlowResult]:
    return dict(self._running_flows)
```

After each `send()` completes, store the result. Expose via a new `flow_status` global
skill so the AI can check whether a long-running flow has completed.

#### 4C. Flow chaining

Add a `chain: list[str]` field to `FlowPayload`. If set, after the current flow
completes successfully, Mycelium automatically dispatches the next action in the chain
with the output of the current one as the new payload.

Example chain: `research → codex → journal` (research note → knowledge entry → reflection)
becomes a single `bus.send("research_to_codex", payload=FlowPayload(chain=["codex_to_journal"]))`.

#### 4D. Add 3 new flows

Extend the current 5 flows with:

- **`operator_to_journal`** — summarise today's completed tasks as a journal entry
- **`codex_to_org`** — turn a knowledge entry into a planning document
- **`journal_to_research`** — extract research themes from journal reflections and create a research note

These follow the same pattern as existing flows: `_first_project_of()` + `_ai_synthesize()` + `_write_*()`.

---

### Phase 5 — Operator as a Formal Sub-Agent

**Files:** `modules/operator/agent.py` (new), `nexus/ai/flow_handlers.py` (modified)

The Operator module is already the most capable unit in Nexus — it has three data layers,
9 skills, and a full GUI. The concept papers suggest formalising sub-agents with typed
input/output contracts. Operator should have a structured agent API callable from other
modules without going through the full AI round-trip.

#### 5A. Create `modules/operator/agent.py`

```python
"""
Operator sub-agent: structured actions callable without an AI round-trip.
Used by other modules and Mycelium flows to read/write Operator data.
"""

@dataclass
class OperatorQuery:
    slug:     str                    # operator project slug to target
    action:   str                    # "calendar_list", "todo_add", "note_search", etc.
    params:   dict = field(default_factory=dict)

@dataclass
class OperatorResult:
    success: bool
    data:    list | dict | str | None = None
    error:   str | None = None

async def query(q: OperatorQuery) -> OperatorResult:
    """Execute an Operator action directly, bypassing AI."""
    ...
```

This is the same logic already in the individual skill handlers, but wrapped in a typed
interface so Mycelium flows and other modules can call Operator deterministically.

#### 5B. Register Operator as a Mycelium target

Add `bus.register_handler("operator_query", _handle_operator_query)` where the handler
creates an `OperatorQuery`, calls `operator_agent.query()`, returns a `FlowResult`.

This enables other modules (e.g., a Journal AI prompt) to ask Operator "what are today's
tasks?" without spawning a full AI client.

---

### Phase 6 — Embedding-Based Memory Layer

**Files:** `nexus/ai/memory.py` (new), `nexus/ai/client.py` (modified)

This is the most ambitious phase and should only be built after Phases 1–3 are stable.

#### 6A. Create `nexus/ai/memory.py`

Two backends:

1. **Ollama embeddings** (when local provider is active): POST to `{local_endpoint}/api/embeddings`
2. **Anthropic text-embedding** (future) or **local sentence-transformers** (CPU-only fallback)

```python
class MemoryStore:
    """Semantic search across Nexus project files."""

    def __init__(self, store_path: Path) -> None:
        self._path  = store_path
        self._index: list[dict] = []   # {text, embedding, source, metadata}

    async def index_file(self, path: Path, source_slug: str) -> None: ...
    async def search(self, query: str, top_k: int = 5) -> list[dict]: ...
    def _cosine(self, a: list[float], b: list[float]) -> float: ...
```

The store is saved as a JSON file alongside the project:
`projects/<slug>/memory_index.json`.

#### 6B. Context injection in `AIClient.chat()`

Before the first model call, optionally retrieve top-k relevant memory chunks and prepend
them to the system prompt:

```python
if self._memory_store and len(messages) > 0:
    last_user_text = ...   # extract last user message text
    chunks = await self._memory_store.search(last_user_text, top_k=3)
    if chunks:
        context_block = "\n\n---\n# Relevant context from your notes:\n" + \
                        "\n---\n".join(c["text"][:500] for c in chunks)
        system_prompt = system_prompt + context_block
```

#### 6C. Memory refresh trigger

Add a `memory_refresh` skill (global scope) that re-indexes a project's notes directory.
The Research and Codex modules can expose a "Refresh Memory Index" button in their GUI screens.

---

### Phase 7 — Promptopt as a Multi-Stage Pipeline

**Files:** `modules/promptopt/gui_screen.py` (modified), `modules/promptopt/project_screen.py` (modified)

The prompt optimizer currently runs one AI call. The papers suggest the strongest reliability
gains come from constraining model output at each stage. Applied to promptopt:

**Pipeline:**

```text
[User Prompt]
    ↓ Stage 1: Mode Classifier
[Detected: text | instruct | image]
    ↓ Stage 2: Structured Decompose
[{intent, constraints, quality_criteria}]
    ↓ Stage 3: Rewrite with Schema
[{optimized_prompt, changes_made}]
    ↓ Stage 4: Validate (length, no hallucinated content, target mode compliance)
[Accept or retry Stage 3]
    ↓ Output
[Optimized Prompt]
```

**Stage 2 JSON schema:**

```json
{
  "intent": "string describing the core goal",
  "style": "string describing tone or format",
  "constraints": ["list of requirements"],
  "weak_elements": ["list of things to improve"]
}
```

**Stage 3 JSON schema:**

```json
{
  "optimized_prompt": "the rewritten prompt",
  "changes_made": ["list of specific improvements"]
}
```

This produces an optimized prompt + a transparent diff of what changed, displayed in the
`_output` log.

The TUI `project_screen.py` should mirror this: show stages in the output log
(`[stage 1/3] classifying mode…`, etc.).

---

## Part 4 — Execution Order and Effort Estimate

| Phase | Effort | Impact | Risk |
| ----- | ------ | ------ | ---- |
| 1 — Pre-execution validation | Low (1–2 days) | High (safety + retry) | Low |
| 2 — Intent-aware tool narrowing | Low (1 day) | High (local AI reliability) | Low |
| 3 — Local AI reliability layer | Medium (2–3 days) | High (for local users) | Low |
| 4 — Mycelium typed contracts + new flows | Medium (2–3 days) | Medium (extensibility) | Medium |
| 5 — Operator sub-agent API | Medium (2 days) | Medium (cross-module power) | Low |
| 6 — Embedding memory | High (3–5 days) | High (Research/Codex UX) | Medium |
| 7 — Promptopt pipeline | Low-Medium (1–2 days) | Medium | Low |

**Recommended order:**

1. Phase 1 (validation) — immediate, no dependencies
2. Phase 2 (intent router) — immediate, no dependencies
3. Phase 3 (local AI) — depends on Phase 1
4. Phase 7 (promptopt) — depends on Phase 1 pattern
5. Phase 5 (operator sub-agent) — depends on Phase 4 contracts
6. Phase 4 (Mycelium) — medium-term
7. Phase 6 (memory) — after stable local AI (Phase 3)

---

## Part 5 — What NOT to Build (Anti-Patterns for Nexus)

### Do not add a separate "small classifier model"

The papers recommend running a tiny classifier model on CPU before the main model. This makes
sense when the main model is a 7B local model that cannot afford multiple roles. In Nexus,
Claude API handles classification + planning + tool-use in one reliable pass. A separate
classifier model would add latency, complexity, and another dependency for marginal gain.
The keyword-based intent router (Phase 2) is sufficient.

### Do not implement grammar-constrained decoding

Grammar-constrained decoding (guiding model token selection via GBNF grammars or similar)
requires deep integration with the inference backend. Ollama supports it, but it is not
exposed via the standard OpenAI-compatible endpoint Nexus uses. Adding it would require
switching `_chat_local()` to the Ollama native API, breaking the clean provider abstraction.
The structured-output prompt injection (Phase 3A) achieves ~80% of the benefit at ~5% of
the complexity.

### Do not load multiple LLMs simultaneously

Even if VRAM allows it, loading a secondary "formatter" model alongside the main model
creates lifecycle management problems (when to load/unload, competing for VRAM during
generation). Nexus is a personal organiser, not an inference server. One model at a time
is the right constraint. Specialised formatting tasks should use deterministic code or
a second sequential call to the same model.

### Do not add ML-based intent classification until rules fail

Embedding-based routing adds a dependency (sentence-transformers or an Ollama embed call)
and latency to every message. Rule-based keyword matching (Phase 2) covers 90% of Nexus's
actual usage patterns. Only upgrade to embedding-based routing if user feedback shows the
keyword router is consistently wrong.

### Do not replace Mycelium with a message queue

The papers mention async pipelines and worker queues. Mycelium's current `await bus.send()`
is simpler and sufficient. Adding a real queue (Redis, Celery, asyncio.Queue) would be
over-engineering for a single-user personal organiser.

---

## Part 6 — New File Map

```text
nexus/ai/
  validator.py          Phase 1 — JSON schema validation + error formatting
  intent_router.py      Phase 2 — keyword-based intent classification
  memory.py             Phase 6 — embedding store + semantic search

modules/operator/
  agent.py              Phase 5 — typed sub-agent query interface

[Modified files]
nexus/ai/client.py      Phase 1C, 3A, 3B, 3C, 3D, 6B
nexus/ai/skill_registry.py     Phase 1B
nexus/ai/flow_handlers.py      Phase 4C, 4D, 5B
nexus/core/mycelium.py         Phase 4A, 4B
nexus/ui/gui/chat_panel.py     Phase 2C
nexus/ui/tui/base_project_screen.py   Phase 2C
modules/promptopt/gui_screen.py        Phase 7
modules/promptopt/project_screen.py   Phase 7
```

---

## Part 7 — Key Design Invariants to Preserve

These principles from the existing codebase must not be violated by any phase above.

1. **AI is a progressive enhancement.** Every module must remain fully functional when
   `is_ai_configured()` returns False. The intent router, validator, and memory store must
   all degrade gracefully to no-ops.

2. **Single provider abstraction.** `AIClient` is the only AI interface. No module should
   import `anthropic` or `httpx` directly. All new AI calls go through `AIClient`.

3. **Skill scopes are the trust boundary.** A module's skills are only exposed when that
   module is active. The intent router may narrow further, but must never expand the scope.

4. **Deterministic code owns structure; AI owns content.** This is already the pattern in
   `flow_handlers.py` (AI synthesises, deterministic code writes files). All new flows
   and pipelines must follow the same split.

5. **No shell=True with user-controlled input.** The Local AI reliability layer generates
   shell commands in some workflows. These must always go through `shlex.split()` +
   `create_subprocess_exec`, not `create_subprocess_shell`.
