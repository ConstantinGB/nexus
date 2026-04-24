from __future__ import annotations
import os
from typing import Any

import anthropic

from nexus.ai.mcp_client import MCPClient
from nexus.ai.skill_registry import registry


class AIClient:
    """Claude API client with MCP tool-use and native Skills support."""

    MODEL = "claude-sonnet-4-6"

    def __init__(self, api_key: str = "", mcp: MCPClient | None = None) -> None:
        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = anthropic.AsyncAnthropic(api_key=key)
        self._mcp = mcp

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        skill_scopes: list[str] | None = None,
    ) -> str:
        """Send messages to Claude, executing tool calls (Skills + MCP) until a final reply.

        skill_scopes: list of scope names to include, e.g. ["global", "git"].
                      Pass None or [] to use only MCP tools.
        """
        mcp_tools   = await self._mcp.get_tools() if self._mcp else []
        skill_tools = registry.get_tools(skill_scopes or [])
        tools       = mcp_tools + skill_tools

        kwargs: dict[str, Any] = {"model": self.MODEL, "max_tokens": 4096, "messages": messages}
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = tools

        while True:
            response = await self._client.messages.create(**kwargs)

            if response.stop_reason == "end_turn" or not tools:
                return "".join(
                    block.text for block in response.content if hasattr(block, "text")
                )

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        if registry.has(block.name):
                            result = await registry.call(block.name, block.input)
                        else:
                            result = await self._mcp.call_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        })

                kwargs["messages"] = [
                    *kwargs["messages"],
                    {"role": "assistant", "content": response.content},
                    {"role": "user", "content": tool_results},
                ]
            else:
                # Unexpected stop reason — return whatever text we have
                return "".join(
                    block.text for block in response.content if hasattr(block, "text")
                )
