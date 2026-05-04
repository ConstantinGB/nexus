from __future__ import annotations
import json
import logging
from typing import Callable, Awaitable

log = logging.getLogger("nexus.skills")


def require_project(slug: str) -> dict:
    """Return project config for *slug*, raising ValueError if the slug is unknown."""
    from nexus.core.project_manager import list_projects
    from nexus.core.config_manager import load_project_config
    if not any(p.slug == slug for p in list_projects()):
        raise ValueError(f"Unknown project slug: {slug!r}")
    return load_project_config(slug)


class SkillRegistry:
    """Registry of native Nexus skills exposed to AI models as tools.

    Skills are in-process Python functions — no external process or config needed.
    Each skill belongs to a scope ('global' or a module id like 'git', 'codex').
    AIClient merges skill tools with MCP tools and dispatches tool_use responses
    to whichever registered the tool name.
    """

    def __init__(self) -> None:
        self._tools: dict[str, dict] = {}   # name -> {scope, description, schema, handler}

    def register(
        self,
        scope: str,
        name: str,
        description: str,
        schema: dict,
        handler: Callable[[dict], Awaitable[str]],
    ) -> None:
        self._tools[name] = {
            "scope":       scope,
            "description": description,
            "schema":      schema,
            "handler":     handler,
        }

    def get_tools(self, scopes: list[str], hints: list[str] | None = None) -> list[dict]:
        """Return Anthropic-format tool dicts for tools whose scope is in *scopes*.

        If *hints* is non-empty, further narrow to tools whose name contains any hint
        substring, always keeping global-scope tools.  Falls back to the full list if
        narrowing would produce an empty result.
        """
        candidates = [
            (name, t) for name, t in self._tools.items()
            if t["scope"] in scopes
        ]
        if hints:
            narrowed = [
                (name, t) for name, t in candidates
                if t["scope"] == "global" or any(h in name for h in hints)
            ]
            if narrowed:
                candidates = narrowed
        return [
            {
                "name":         name,
                "description":  t["description"],
                "input_schema": t["schema"],
            }
            for name, t in candidates
        ]

    async def call(self, name: str, args: dict) -> str:
        from nexus.ai.validator import validate_args, ValidationError
        entry = self._tools.get(name)
        if entry is None:
            return json.dumps({"error": f"Unknown skill: {name!r}"})
        try:
            validate_args(name, args, entry["schema"])
            return await entry["handler"](args)
        except ValidationError as exc:
            log.warning("Skill %s arg validation failed: %s", name, exc.errors)
            return json.dumps({"validation_error": exc.errors, "tool": name, "schema": entry["schema"]})
        except Exception as exc:
            log.exception("Skill %r raised an exception", name)
            return json.dumps({"error": str(exc)})

    def has(self, name: str) -> bool:
        return name in self._tools

    def all_scopes(self) -> list[str]:
        return list({t["scope"] for t in self._tools.values()})


registry = SkillRegistry()
