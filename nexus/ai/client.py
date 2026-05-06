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


_MAX_TOOL_ITERATIONS = 10

# Providers that use the OpenAI-compatible chat endpoint
_OAI_COMPAT_PROVIDERS = {"local", "openwebui", "openai_compat"}


class AIClient:
    """Multi-provider AI client with MCP tool-use and native Skills support.

    Providers:
      anthropic    — Anthropic API (Claude models)
      openwebui    — OpenWebUI instance (OpenAI-compat at /api/v1/)
      openai_compat — any OpenAI-compatible endpoint
      local        — Ollama or similar (no auth header)
    """

    MODEL = "claude-sonnet-4-6"

    def __init__(
        self,
        api_key: str = "",
        mcp: MCPClient | None = None,
        force_provider: str = "",
    ) -> None:
        cfg = load_global_config().get("ai", {})
        provider = force_provider or cfg.get("provider", "anthropic")
        # Normalise legacy alias
        if provider == "api_key":
            provider = "anthropic"
        self._provider = provider
        self._mcp      = mcp

        providers_cfg = cfg.get("providers", {})

        if provider in _OAI_COMPAT_PROVIDERS:
            self._anthropic        = None
            self._local_auth_header: dict[str, str] = {}

            if provider == "openwebui":
                p = providers_cfg.get("openwebui", {})
                base = p.get("base_url", "http://localhost:3000").rstrip("/")
                # OpenWebUI exposes the OpenAI-compat API at /api
                self._local_endpoint = base + "/api"
                key = p.get("api_key", "")
                if key:
                    self._local_auth_header = {"Authorization": f"Bearer {key}"}
                self._local_model = p.get("model", "")

            elif provider == "openai_compat":
                p = providers_cfg.get("openai_compat", {})
                self._local_endpoint = p.get("base_url", "").rstrip("/")
                key = p.get("api_key", "")
                if key:
                    self._local_auth_header = {"Authorization": f"Bearer {key}"}
                self._local_model = p.get("model", "")

            else:  # local (Ollama)
                p = providers_cfg.get("local", {})
                self._local_endpoint = (
                    p.get("endpoint") or cfg.get("local_endpoint", "http://localhost:11434")
                ).rstrip("/")
                self._local_model = p.get("model") or cfg.get("local_model", "")

        else:  # anthropic
            p = providers_cfg.get("anthropic", {})
            resolved_key = (
                api_key
                or p.get("api_key", "")
                or cfg.get("api_key", "")
                or os.environ.get("ANTHROPIC_API_KEY", "")
            )
            self._anthropic = anthropic.AsyncAnthropic(api_key=resolved_key)

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        skill_scopes: list[str] | None = None,
        intent: dict | None = None,
    ) -> str:
        if self._provider in _OAI_COMPAT_PROVIDERS:
            return await self._chat_local(messages, system_prompt, skill_scopes, intent)
        return await self._chat_anthropic(messages, system_prompt, skill_scopes, intent)

    async def _chat_anthropic(
        self,
        messages: list[dict],
        system_prompt: str = "",
        skill_scopes: list[str] | None = None,
        intent: dict | None = None,
    ) -> str:
        hints       = intent.get("intra_scope_hints") if intent else None
        mcp_tools   = await self._mcp.get_tools() if self._mcp else []
        skill_tools = registry.get_tools(skill_scopes or [], hints=hints)
        tools       = mcp_tools + skill_tools
        if intent and not intent.get("likely_tool_use", True):
            tools = []

        kwargs: dict[str, Any] = {"model": self.MODEL, "max_tokens": 4096, "messages": messages}
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = tools

        for _iteration in range(_MAX_TOOL_ITERATIONS):
            response = await self._anthropic.messages.create(**kwargs)

            if response.stop_reason == "end_turn" or not tools:
                return "".join(
                    block.text for block in response.content if hasattr(block, "text")
                )

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        try:
                            if registry.has(block.name):
                                result = await registry.call(block.name, block.input)
                            else:
                                result = await self._mcp.call_tool(block.name, block.input)
                            is_error = False
                        except Exception as exc:
                            result = json.dumps({"error": str(exc)})
                            is_error = True
                        try:
                            result_dict = json.loads(result)
                            if "validation_error" in result_dict:
                                result = (
                                    f"Your arguments for '{block.name}' were invalid: "
                                    f"{result_dict['validation_error']}. "
                                    f"Schema requires: {result_dict.get('schema', {})}. "
                                    "Please retry with valid arguments."
                                )
                                is_error = True
                        except (ValueError, TypeError):
                            pass
                        tool_results.append({
                            "type":        "tool_result",
                            "tool_use_id": block.id,
                            "content":     str(result),
                            **({"is_error": True} if is_error else {}),
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
        return "[Error] Tool-use loop exceeded maximum iterations."

    async def _chat_local(
        self,
        messages: list[dict],
        system_prompt: str = "",
        skill_scopes: list[str] | None = None,
        intent: dict | None = None,
    ) -> str:
        import httpx
        hints       = intent.get("intra_scope_hints") if intent else None
        skill_tools = registry.get_tools(skill_scopes or [], hints=hints)
        mcp_tools   = await self._mcp.get_tools() if self._mcp else []
        oai_tools   = [_to_oai_tool(t) for t in skill_tools + mcp_tools]
        if intent and not intent.get("likely_tool_use", True):
            oai_tools = []

        oai_msgs: list[dict] = []
        if system_prompt:
            oai_msgs.append({"role": "system", "content": system_prompt})
        oai_msgs.extend(messages)

        headers = dict(self._local_auth_header)

        async with httpx.AsyncClient(timeout=120.0) as http:
            for _iteration in range(_MAX_TOOL_ITERATIONS):
                body: dict[str, Any] = {"messages": oai_msgs}
                if self._local_model:
                    body["model"] = self._local_model
                if oai_tools:
                    body["tools"] = oai_tools

                try:
                    r = await http.post(
                        f"{self._local_endpoint}/v1/chat/completions",
                        json=body,
                        headers=headers,
                    )
                    r.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 400 and oai_tools:
                        import logging
                        logging.getLogger("nexus.ai.client").warning(
                            "Local endpoint 400 with tools; retrying without tools: %s",
                            exc.response.text[:200],
                        )
                        oai_tools = []
                        continue
                    return f"[Error {exc.response.status_code}] {exc.response.text[:300]}"
                except httpx.ConnectError:
                    return "[Error] Could not connect to local endpoint — is the server running?"
                except httpx.ReadTimeout:
                    return "[Error] Local endpoint timed out."
                except Exception as exc:
                    return f"[Error] {exc}"

                try:
                    choices = r.json().get("choices", [])
                except (ValueError, KeyError):
                    choices = []
                if not choices:
                    return ""
                choice = choices[0]
                msg    = choice.get("message", {})

                if choice.get("finish_reason") != "tool_calls" or not msg.get("tool_calls"):
                    return msg.get("content") or ""

                oai_msgs.append(msg)
                for tc in msg["tool_calls"]:
                    name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        args = {}
                    try:
                        if registry.has(name):
                            result = await registry.call(name, args)
                        elif self._mcp:
                            result = await self._mcp.call_tool(name, args)
                        else:
                            result = json.dumps({"error": f"Unknown tool: {name}"})
                    except Exception as exc:
                        result = json.dumps({"error": str(exc)})
                    try:
                        result_dict = json.loads(result)
                        if "validation_error" in result_dict:
                            result = (
                                f"Your arguments for '{name}' were invalid: "
                                f"{result_dict['validation_error']}. "
                                f"Schema requires: {result_dict.get('schema', {})}. "
                                "Please retry with valid arguments."
                            )
                    except (ValueError, TypeError):
                        pass
                    oai_msgs.append({
                        "role":         "tool",
                        "tool_call_id": tc["id"],
                        "content":      str(result),
                    })
            return "[Error] Tool-use loop exceeded maximum iterations."
