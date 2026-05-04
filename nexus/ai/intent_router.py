from __future__ import annotations

# Per-module keyword signals for intra-scope hint matching
_SCOPE_HINTS: dict[str, list[str]] = {
    "calendar":  ["event", "meeting", "appointment", "schedule", "calendar", "remind", "today", "tomorrow"],
    "notes":     ["note", "write", "draft", "document", "record", "memo"],
    "todo":      ["task", "todo", "do", "complete", "finish", "deadline", "priority"],
    "git":       ["commit", "push", "pull", "branch", "repo", "diff", "stash", "merge", "clone"],
    "research":  ["research", "paper", "find", "search", "analyse", "analyze", "literature", "source"],
    "codex":     ["codex", "knowledge", "zettelkasten", "entry", "concept", "idea", "definition"],
    "journal":   ["journal", "diary", "reflection", "log", "write about", "daily"],
    "org":       ["plan", "project", "roadmap", "outline", "org", "strategy", "milestone"],
    "backup":    ["backup", "snapshot", "restore", "restic", "archive"],
    "vault":     ["encrypt", "decrypt", "key", "gpg", "vault", "password", "secret", "age"],
    "security":  ["firewall", "vpn", "audit", "nmap", "ports", "fail2ban", "scan", "exploit"],
    "localai":   ["ollama", "local model", "inference", "generate", "stable diffusion", "image gen"],
    "promptopt": ["prompt", "optimize", "improve", "rewrite prompt", "prompt engineer"],
    "operator":  ["operator", "brief", "summary", "today", "overview"],
    "youtube":   ["youtube", "video", "download", "url", "watch"],
    "streaming": ["obs", "stream", "scene", "overlay", "broadcast"],
    "emulator":  ["emulator", "rom", "retroarch", "system", "game", "play"],
}

# Action verbs that strongly suggest a tool call is needed
_TOOL_TRIGGER_WORDS: frozenset[str] = frozenset({
    "create", "add", "new", "make", "insert",
    "delete", "remove", "clear", "drop",
    "update", "edit", "change", "set", "rename",
    "list", "show", "get", "find", "search", "fetch", "display",
    "run", "execute", "start", "stop", "launch", "kill",
    "backup", "restore", "sync", "push", "pull", "clone",
    "open", "read", "write", "save", "export", "import",
    "check", "verify", "test", "scan", "audit",
    "generate", "optimize", "compile", "build",
})

_CONJUNCTIONS: tuple[str, ...] = (" and ", " then ", " also ", " after ", " before ", " while ")


def classify(text: str, active_module: str) -> dict:
    """
    Returns:
        {
            "likely_tool_use": bool,
            "intra_scope_hints": list[str],
            "complexity": "simple" | "moderate" | "complex",
        }
    """
    lower = text.lower()
    words = set(lower.split())

    likely_tool = bool(words & _TOOL_TRIGGER_WORDS) or "?" not in text

    intra_hints = [
        scope for scope, keywords in _SCOPE_HINTS.items()
        if any(kw in lower for kw in keywords)
    ]

    word_count   = len(text.split())
    conjunctions = sum(lower.count(c) for c in _CONJUNCTIONS)

    if word_count < 8 and conjunctions == 0:
        complexity: str = "simple"
    elif word_count > 40 or conjunctions >= 2:
        complexity = "complex"
    else:
        complexity = "moderate"

    return {
        "likely_tool_use":    likely_tool,
        "intra_scope_hints":  intra_hints,
        "complexity":         complexity,
    }
