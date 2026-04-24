from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class MCPServerSpec:
    id: str
    name: str
    description: str
    command: str
    args: list[str]
    required_env: list[str] = field(default_factory=list)
    optional_env: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def default_config(self) -> dict:
        return {
            "command": self.command,
            "args": self.args,
            "env": {k: "" for k in self.required_env + self.optional_env},
        }


REGISTRY: list[MCPServerSpec] = [
    MCPServerSpec(
        id="filesystem",
        name="Filesystem",
        description="Read and write files on your local machine. Provide a root path to restrict access.",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "~"],
        tags=["files", "local"],
    ),
    MCPServerSpec(
        id="github",
        name="GitHub",
        description="Browse repos, read issues and PRs, search code on GitHub.",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        required_env=["GITHUB_TOKEN"],
        tags=["git", "dev"],
    ),
    MCPServerSpec(
        id="memory",
        name="Memory",
        description="Persistent key-value memory that survives across AI sessions.",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-memory"],
        tags=["memory", "storage"],
    ),
    MCPServerSpec(
        id="brave-search",
        name="Brave Search",
        description="Web search via the Brave Search API. Requires a free API key.",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-brave-search"],
        required_env=["BRAVE_API_KEY"],
        tags=["search", "web"],
    ),
    MCPServerSpec(
        id="fetch",
        name="Fetch",
        description="Fetch and read the content of any web page or URL.",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-fetch"],
        tags=["web", "research"],
    ),
    MCPServerSpec(
        id="sqlite",
        name="SQLite",
        description="Query and modify a local SQLite database file.",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-sqlite", "--db-path", "~/nexus.db"],
        tags=["database", "local"],
    ),
    MCPServerSpec(
        id="puppeteer",
        name="Puppeteer",
        description="Control a real browser — take screenshots, click, fill forms, scrape pages.",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-puppeteer"],
        tags=["browser", "automation", "web"],
    ),
]

REGISTRY_BY_ID: dict[str, MCPServerSpec] = {s.id: s for s in REGISTRY}
