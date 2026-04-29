from __future__ import annotations
import json

from nexus.ai.skill_registry import registry


async def _promptopt_optimize(args: dict) -> str:
    prompt = args.get("prompt", "").strip()
    mode   = args.get("mode", "text")

    system_prompts = {
        "text": (
            "Rewrite the following prompt to be more precise, unambiguous, and AI-readable. "
            "Return only the improved prompt, no explanation."
        ),
        "instruct": (
            "Rewrite the following as a clear AI instruction. Use imperative tone, explicit "
            "constraints, and structured formatting. Return only the rewritten instruction."
        ),
        "image": (
            "Convert the following natural-language image description into a comma-separated "
            "tag-based prompt optimised for Stable Diffusion. Include style, lighting, "
            "composition, and quality tags. Return only the tag prompt."
        ),
    }

    if not prompt:
        return json.dumps({"error": "prompt is required"})
    if mode not in system_prompts:
        return json.dumps({"error": f"invalid mode: {mode}"})

    try:
        from nexus.core.config_manager import is_ai_configured
        if not is_ai_configured():
            return json.dumps({"error": "AI not configured"})
        from nexus.ai.client import AIClient
        client = AIClient()
        result = await client.chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=system_prompts[mode],
        )
        return json.dumps({"result": result})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "promptopt",
    name        = "promptopt_optimize",
    description = "Optimize a prompt for a given mode: text, instruct, or image.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "prompt":       {"type": "string", "description": "The raw input prompt to optimize"},
            "mode":         {
                "type": "string",
                "enum": ["text", "instruct", "image"],
                "description": "Optimization mode",
            },
        },
        "required": ["project_slug", "prompt", "mode"],
    },
    handler = _promptopt_optimize,
)
