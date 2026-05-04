---
description: AIClient, skill registry, MCP integration, Mycelium flows, and provider configuration
paths:
  - "nexus/ai/**"
  - "nexus/core/config_manager.py"
  - "nexus/core/mycelium.py"
---

## AI Provider Configuration

Configured via `config/settings.yaml` or the Settings screen (`s`).

| Provider | Behaviour |
|----------|-----------|
| `api_key` | Anthropic key → `AIClient._chat_anthropic()` via `AsyncAnthropic` |
| `local` | OpenAI-compatible endpoint → `AIClient._chat_local()` via `httpx`; tools translated with `_to_oai_tool()`; degrades gracefully when model doesn't support function calling |
| `login` | Claude.ai OAuth — not yet supported in terminal UI |

`is_ai_configured(cfg=None) -> bool` in `config_manager.py` is the single source of truth — use it, don't check for a key directly. `api_key` requires a key or `ANTHROPIC_API_KEY` env var; `local` requires both `local_endpoint` and `local_model`.

## AIClient.chat()

```python
reply = await ai_client.chat(
    messages      = conversation,          # list of {role, content} dicts
    system_prompt = project_system_prompt,
    skill_scopes  = ["global", project.module],
    max_iterations = 10,                   # tool-use loop limit
)
```

Merges skills + MCP tools into one list. On `tool_use` response: tries skill registry first, falls through to `MCPClient.call_tool()` if not found.

**Local model degradation:** if the endpoint returns HTTP 400 when tools are passed, `_chat_local` retries without tools and logs a WARNING. This is expected behaviour with models that don't support function calling.

## Skill Registry

```python
from nexus.ai.skill_registry import registry

registry.register(
    scope       = "git",           # "global" or module id
    name        = "git_pull",
    description = "Pull the latest commits for a named repository.",
    schema      = {"type": "object", "properties": {"repo": {"type": "string"}}, "required": ["repo"]},
    handler     = my_async_fn,     # async (args: dict) -> str
)
```

| Method | Description |
|--------|-------------|
| `registry.register(scope, name, description, schema, handler)` | Register one skill |
| `registry.get_tools(scopes)` | Anthropic-format tool dicts for the given scopes |
| `registry.call(name, args)` | Await the handler |
| `registry.all_scopes()` | All registered scopes |

**Scope conventions:**

- `"global"` — loaded in every context
- `"<module_id>"` — loaded when a project of that module type is active

Skills are registered at import time in `modules/<id>/skills.py`. `nexus/app.py` imports all skills modules at startup in `_register_skills()`.

**Global skills:** `list_projects`, `run_flow(action, payload)`, `search_logs(query?, n=50)`

## MCP Integration

```
config/settings.yaml  ──► ConfigManager ──► MCPClient (connects to servers)
projects/<name>/config.yaml ──►┘              └──► AIClient (passes tools to Claude)
```

Key files: `mcp_client.py` (`connect_all`, `get_tools`, `call_tool`, `disconnect_all`), `mcp_registry.py` (curated catalog), `mcp_screen.py` (Active / Add Servers tabs).

Per-project config can add servers or disable global ones:

```yaml
mcp:
  servers:
    sqlite:
      command: npx
      args: ["-y", "@modelcontextprotocol/server-sqlite", "--db-path", "./data.db"]
  disabled:
    - brave-search
```

## Mycelium — Cross-Module Flows

`nexus/core/mycelium.py` singleton `bus`. `register_flow_handlers()` in `nexus/ai/flow_handlers.py` wires up five default flows at startup:

| Source | Target | Flow |
|--------|--------|------|
| `research` | `codex` | distil findings into a knowledge entry |
| `git` | `journal` | summarise recent commits |
| `research` | `org` | turn notes into a plan |
| `codex` | `journal` | reflect on a topic |
| `org` | `journal` | log completed tasks |

Invoke via the `run_flow` global skill. Each handler calls `_ai_synthesize()` which respects the active AI provider.
