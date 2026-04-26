from __future__ import annotations

import json
from pathlib import Path

from nexus.ai.skill_registry import registry
from nexus.core.config_manager import load_project_config
from nexus.core.logger import get

log = get("skills.sdforge")

_PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"


def _sdforge_cfg(slug: str) -> dict:
    return load_project_config(slug).get("sdforge", {})


async def _sdforge_txt2img(args: dict) -> str:
    slug      = args["project_slug"]
    prompt    = args["prompt"]
    cfg       = _sdforge_cfg(slug)
    endpoint  = cfg.get("endpoint", "http://localhost:7860").rstrip("/")

    if not endpoint:
        return json.dumps({"error": "No endpoint configured for this SDForge project."})

    neg_prompt  = args.get("negative_prompt", "")
    width       = int(args.get("width",  512))
    height      = int(args.get("height", 512))
    steps       = int(args.get("steps",  20))
    cfg_scale   = float(args.get("cfg_scale", 7.0))
    sampler     = args.get("sampler_name", "Euler a")
    seed        = int(args.get("seed", -1))

    out_dir_rel = cfg.get("output_dir", "outputs/")
    output_dir  = _PROJECTS_DIR / slug / out_dir_rel

    try:
        from modules.sdforge.api_client import txt2img, save_image
        images = await txt2img(
            endpoint, prompt, neg_prompt,
            width=width, height=height, steps=steps,
            cfg_scale=cfg_scale, sampler_name=sampler, seed=seed,
        )
        saved = save_image(images[0], output_dir, prefix="skill_img")
        return json.dumps({"success": True, "saved_path": str(saved)})
    except Exception as exc:
        log.exception("sdforge_txt2img skill failed for project %s", slug)
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "sdforge",
    name        = "sdforge_txt2img",
    description = (
        "Generate an image using Stable Diffusion Forge (txt2img). "
        "The SD Forge server must already be running at the configured endpoint. "
        "Returns the path to the saved PNG file."
    ),
    schema = {
        "type": "object",
        "properties": {
            "project_slug":    {"type": "string",  "description": "The sdforge project slug"},
            "prompt":          {"type": "string",  "description": "Text prompt"},
            "negative_prompt": {"type": "string",  "description": "Negative prompt (optional)"},
            "width":           {"type": "integer", "description": "Image width in pixels (default 512)"},
            "height":          {"type": "integer", "description": "Image height in pixels (default 512)"},
            "steps":           {"type": "integer", "description": "Sampling steps (default 20)"},
            "cfg_scale":       {"type": "number",  "description": "CFG / guidance scale (default 7.0)"},
            "sampler_name":    {"type": "string",  "description": "Sampler name (default 'Euler a')"},
            "seed":            {"type": "integer", "description": "Seed, -1 for random (default -1)"},
        },
        "required": ["project_slug", "prompt"],
    },
    handler = _sdforge_txt2img,
)
