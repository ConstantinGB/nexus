from __future__ import annotations
import json
from typing import Callable, Awaitable


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

    def get_tools(self, scopes: list[str]) -> list[dict]:
        """Return Anthropic-format tool dicts for tools whose scope is in *scopes*."""
        return [
            {
                "name":         name,
                "description":  t["description"],
                "input_schema": t["schema"],
            }
            for name, t in self._tools.items()
            if t["scope"] in scopes
        ]

    async def call(self, name: str, args: dict) -> str:
        entry = self._tools.get(name)
        if entry is None:
            return json.dumps({"error": f"Unknown skill: {name!r}"})
        return await entry["handler"](args)

    def has(self, name: str) -> bool:
        return name in self._tools

    def all_scopes(self) -> list[str]:
        return list({t["scope"] for t in self._tools.values()})


registry = SkillRegistry()
