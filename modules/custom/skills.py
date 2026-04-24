from __future__ import annotations
import asyncio
import json
from pathlib import Path

from nexus.ai.skill_registry import registry
from nexus.core.config_manager import load_global_config, load_project_config
from nexus.core.logger import get

log = get("skills.custom")

_PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"


# ── custom_run_command ────────────────────────────────────────────────────────

async def _custom_run_command(args: dict) -> str:
    slug  = args["project_slug"]
    label = args["label"]

    cfg      = load_project_config(slug)
    commands = cfg.get("custom", {}).get("commands", [])
    match    = next((c for c in commands if c["label"] == label), None)

    if not match:
        available = [c["label"] for c in commands]
        return json.dumps({
            "error": f"No command named '{label}'.",
            "available": available,
        })

    cmd = match["cmd"]
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(_PROJECTS_DIR / slug),
        )
        out, _ = await proc.communicate()
        output = out.decode(errors="replace").strip()
        return json.dumps({"success": proc.returncode == 0, "output": output})
    except Exception as exc:
        log.exception("custom_run_command failed: %s", cmd)
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "custom",
    name        = "custom_run_command",
    description = "Run a named custom shell command defined in a Custom project.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string", "description": "Nexus project slug"},
            "label":        {"type": "string", "description": "Command label as shown in the UI"},
        },
        "required": ["project_slug", "label"],
    },
    handler = _custom_run_command,
)


# ── custom_ask ────────────────────────────────────────────────────────────────

async def _custom_ask(args: dict) -> str:
    slug     = args["project_slug"]
    question = args["question"]

    md_path = _PROJECTS_DIR / slug / "CLAUDE.md"
    try:
        claude_md = md_path.read_text(errors="replace")
    except FileNotFoundError:
        return json.dumps({"error": f"CLAUDE.md not found for project '{slug}'."})

    from nexus.core.config_manager import is_ai_configured
    if not is_ai_configured(load_global_config().get("ai", {})):
        return json.dumps({"error": "No AI provider configured — add one in Settings."})

    try:
        from nexus.ai.client import AIClient
        client = AIClient()
        reply  = await client.chat(
            messages      = [{"role": "user", "content": question}],
            system_prompt = claude_md,
            skill_scopes  = [],
        )
        return json.dumps({"reply": reply})
    except Exception as exc:
        log.exception("custom_ask failed for %s", slug)
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "custom",
    name        = "custom_ask",
    description = (
        "Ask the AI a question about a Custom project, using that project's CLAUDE.md "
        "as context. Useful for cross-module AI orchestration."
    ),
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string", "description": "Nexus project slug"},
            "question":     {"type": "string", "description": "Question to ask"},
        },
        "required": ["project_slug", "question"],
    },
    handler = _custom_ask,
)
