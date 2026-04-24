from __future__ import annotations
import asyncio
import json
from pathlib import Path

from nexus.ai.skill_registry import registry
from nexus.core.config_manager import load_project_config
from nexus.core.logger import get

log = get("skills.web")


def _web_cfg(slug: str) -> dict:
    return load_project_config(slug).get("web", {})


# ---------------------------------------------------------------------------
# web_list_scripts
# ---------------------------------------------------------------------------

async def _web_list_scripts(args: dict) -> str:
    slug = args["project_slug"]
    cfg  = _web_cfg(slug)
    raw  = cfg.get("project_path", "")
    if not raw:
        return json.dumps({"error": "project_path not configured"})
    pkg = Path(raw).expanduser() / "package.json"
    if not pkg.exists():
        return json.dumps({"scripts": {}, "note": "package.json not found"})
    try:
        data    = json.loads(pkg.read_text(encoding="utf-8"))
        scripts = data.get("scripts", {})
        return json.dumps({"scripts": scripts})
    except Exception as exc:
        log.exception("web_list_scripts skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "web",
    name        = "web_list_scripts",
    description = "Return the scripts defined in the project's package.json.",
    schema      = {
        "type": "object",
        "properties": {"project_slug": {"type": "string"}},
        "required": ["project_slug"],
    },
    handler = _web_list_scripts,
)


# ---------------------------------------------------------------------------
# web_run_script
# ---------------------------------------------------------------------------

async def _web_run_script(args: dict) -> str:
    slug   = args["project_slug"]
    script = args["script"]
    cfg    = _web_cfg(slug)
    raw    = cfg.get("project_path", "")
    pm     = cfg.get("package_manager", "npm")
    if not raw:
        return json.dumps({"error": "project_path not configured"})
    cwd = Path(raw).expanduser()
    try:
        proc = await asyncio.create_subprocess_exec(
            pm, "run", script,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            cwd=str(cwd),
        )
        out, _ = await proc.communicate()
        return json.dumps({"output": out.decode(errors="replace").strip(),
                           "returncode": proc.returncode})
    except FileNotFoundError:
        return json.dumps({"error": f"'{pm}' not found on PATH"})
    except Exception as exc:
        log.exception("web_run_script skill failed")
        return json.dumps({"error": str(exc)})


registry.register(
    scope       = "web",
    name        = "web_run_script",
    description = "Run a package.json script (e.g. dev, build, test, lint) via the configured package manager.",
    schema      = {
        "type": "object",
        "properties": {
            "project_slug": {"type": "string"},
            "script":       {"type": "string", "description": "Script name from package.json scripts"},
        },
        "required": ["project_slug", "script"],
    },
    handler = _web_run_script,
)
