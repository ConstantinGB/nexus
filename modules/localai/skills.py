from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path

from nexus.ai.skill_registry import registry
from nexus.core.config_manager import load_project_config
from nexus.core.logger import get

log = get("skills.localai")

_PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"


def _localai_cfg(slug: str) -> dict:
    return load_project_config(slug).get("localai", {})


# ---------------------------------------------------------------------------
# localai_run_inference
# ---------------------------------------------------------------------------

async def _localai_run_inference(args: dict) -> str:
    slug            = args["project_slug"]
    prompt          = args["prompt"]
    negative_prompt = args.get("negative_prompt", "")

    cfg         = _localai_cfg(slug)
    run_command = cfg.get("run_command", "")
    if not run_command:
        return json.dumps({"error": "No run_command configured for this LocalAI project."})

    # Replace legacy placeholders with env var references (same as project_screen)
    cmd = run_command
    cmd = cmd.replace("{prompt}",          "$NEXUS_PROMPT")
    cmd = cmd.replace("{negative_prompt}", "$NEXUS_NEGATIVE_PROMPT")

    env                        = os.environ.copy()
    env["NEXUS_PROMPT"]          = prompt
    env["NEXUS_NEGATIVE_PROMPT"] = negative_prompt

    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(_PROJECTS_DIR / slug),
            env=env,
        )
        out, _ = await proc.communicate()
        output = out.decode(errors="replace").strip()
        return json.dumps({"success": proc.returncode == 0, "output": output})
    except Exception as exc:
        log.exception("localai_run_inference failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "localai",
    name        = "localai_run_inference",
    description = "Run inference using the configured LocalAI command for a project. Returns the captured output.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug":    {"type": "string"},
            "prompt":          {"type": "string", "description": "The input prompt"},
            "negative_prompt": {"type": "string", "description": "Optional negative prompt (image models)"},
        },
        "required": ["project_slug", "prompt"],
    },
    handler = _localai_run_inference,
)
