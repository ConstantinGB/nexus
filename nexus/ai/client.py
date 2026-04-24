from __future__ import annotations
import json
import os
from typing import Any

import anthropic

from nexus.ai.mcp_client import MCPClient
from nexus.ai.skill_registry import registry
from nexus.core.config_manager import load_global_config


def _to_oai_tool(tool: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name":        tool["name"],
            "description": tool.get("description", ""),
            "parameters":  tool.get("input_schema", {}),
        },
    }


class AIClient:
    """Claude API client with MCP tool-use and native Skills support."""

    MODEL = "claude-sonnet-4-6"

    def __init__(self, api_key: str = "", mcp: MCPClient | None = None) -> None:
        cfg = load_global_config().get("ai", {})
        self._provider = cfg.get("provider", "api_key")
        if self._provider == "local":
            self._local_endpoint = cfg.get("local_endpoint", "http://localhost:11434").rstrip("/")
            self._local_model    = cfg.get("local_model", "")
            self._anthropic      = None
        else:
            key = api_key or cfg.get("api_key", "") or os.environ.get("ANTHROPIC_API_KEY", "")
            self._anthropic = anthropic.AsyncAnthropic(api_key=key)
        self._mcp = mcp

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        skill_scopes: list[str] | None = None,
    ) -> str:
        if self._provider == "local":
            return await self._chat_local(messages, system_prompt, skill_scopes)
        return await self._chat_anthropic(messages, system_prompt, skill_scopes)

    async def _chat_anthropic(
        self,
        messages: list[dict],
        system_prompt: str = "",
        skill_scopes: list[str] | None = None,
    ) -> str:
        mcp_tools   = await self._mcp.get_tools() if self._mcp else []
        skill_tools = registry.get_tools(skill_scopes or [])
        tools       = mcp_tools + skill_tools

        kwargs: dict[str, Any] = {"model": self.MODEL, "max_tokens": 4096, "messages": messages}
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = tools

        while True:
            response = await self._anthropic.messages.create(**kwargs)

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
                return "".join(
                    block.text for block in response.content if hasattr(block, "text")
                )

    async def _chat_local(
        self,
        messages: list[dict],
        system_prompt: str = "",
        skill_scopes: list[str] | None = None,
    ) -> str:
        import httpx
        skill_tools = registry.get_tools(skill_scopes or [])
        mcp_tools   = await self._mcp.get_tools() if self._mcp else []
        oai_tools   = [_to_oai_tool(t) for t in skill_tools + mcp_tools]

        oai_msgs: list[dict] = []
        if system_prompt:
            oai_msgs.append({"role": "system", "content": system_prompt})
        oai_msgs.extend(messages)

        async with httpx.AsyncClient(timeout=120.0) as http:
            while True:
                body: dict[str, Any] = {
                    "model":    self._local_model,
                    "messages": oai_msgs,
                }
                if oai_tools:
                    body["tools"] = oai_tools

                try:
                    r = await http.post(
                        f"{self._local_endpoint}/v1/chat/completions",
                        json=body,
                    )
                    r.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 400 and oai_tools:
                        oai_tools = []
                        continue
                    raise

                choice = r.json()["choices"][0]
                msg    = choice["message"]

                if choice.get("finish_reason") != "tool_calls" or not msg.get("tool_calls"):
                    return msg.get("content") or ""

                oai_msgs.append(msg)
                for tc in msg["tool_calls"]:
                    name   = tc["function"]["name"]
                    args   = json.loads(tc["function"]["arguments"])
                    if registry.has(name):
                        result = await registry.call(name, args)
                    elif self._mcp:
                        result = await self._mcp.call_tool(name, args)
                    else:
                        result = json.dumps({"error": f"Unknown tool: {name}"})
                    oai_msgs.append({
                        "role":         "tool",
                        "tool_call_id": tc["id"],
                        "content":      str(result),
                    })
