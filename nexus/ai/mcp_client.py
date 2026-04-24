from __future__ import annotations
import asyncio
import os
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from nexus.core.logger import get

log = get("ai.mcp_client")


class MCPClient:
    """Manages connections to one or more MCP servers."""

    def __init__(self) -> None:
        self._sessions: dict[str, ClientSession] = {}
        self._tool_index: dict[str, str] = {}  # tool_name -> server_id
        self._stack = AsyncExitStack()

    async def connect_all(self, servers: dict[str, dict]) -> None:
        log.info("Connecting to %d MCP server(s): %s", len(servers), list(servers.keys()))
        await self._stack.__aenter__()
        for server_id, cfg in servers.items():
            try:
                await self._connect_one(server_id, cfg)
            except Exception:
                log.exception("Could not connect to MCP server: %s", server_id)

    async def _connect_one(self, server_id: str, cfg: dict) -> None:
        log.debug("Connecting to MCP server: %s (command=%s)", server_id, cfg.get("command"))
        env = {**os.environ, **{k: v for k, v in cfg.get("env", {}).items() if v}}
        params = StdioServerParameters(
            command=cfg["command"],
            args=cfg.get("args", []),
            env=env,
        )
        read, write = await self._stack.enter_async_context(stdio_client(params))
        session = await self._stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._sessions[server_id] = session

        tools_result = await session.list_tools()
        tool_names = [t.name for t in tools_result.tools]
        for name in tool_names:
            self._tool_index[name] = server_id
        log.info("Connected to %s — %d tools: %s", server_id, len(tool_names), tool_names)

    async def get_tools(self) -> list[dict]:
        tools = []
        for server_id, session in self._sessions.items():
            try:
                result = await session.list_tools()
                for tool in result.tools:
                    tools.append({
                        "name": tool.name,
                        "description": tool.description or "",
                        "input_schema": tool.inputSchema,
                    })
            except Exception:
                log.exception("Failed to list tools for server: %s", server_id)
        log.debug("get_tools: returning %d tools total", len(tools))
        return tools

    async def call_tool(self, name: str, arguments: dict) -> Any:
        server_id = self._tool_index.get(name)
        if server_id is None:
            log.error("call_tool: unknown tool %r", name)
            raise ValueError(f"Unknown tool: {name!r}")
        log.debug("call_tool: %s (server=%s)", name, server_id)
        session = self._sessions[server_id]
        try:
            result = await session.call_tool(name, arguments)
        except Exception:
            log.exception("call_tool failed: %s", name)
            raise
        return result.content

    async def disconnect_all(self) -> None:
        log.info("Disconnecting all MCP servers: %s", list(self._sessions.keys()))
        try:
            await self._stack.__aexit__(None, None, None)
        except Exception:
            log.exception("Error during MCP disconnect")
        finally:
            self._sessions.clear()
            self._tool_index.clear()
            log.debug("MCP sessions cleared")

    @property
    def connected_servers(self) -> list[str]:
        return list(self._sessions.keys())
