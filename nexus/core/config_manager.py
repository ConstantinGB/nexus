from __future__ import annotations
import os
from pathlib import Path
import yaml

from nexus.core.logger import get

log = get("core.config_manager")

_ROOT = Path(__file__).parent.parent.parent
_GLOBAL_CONFIG = _ROOT / "config" / "settings.yaml"
_PROJECTS_DIR = _ROOT / "projects"

_DEFAULT_CONFIG: dict = {
    "ai": {
        "provider":       "api_key",
        "api_key":        "",
        "local_endpoint": "http://localhost:11434",
        "local_model":    "",
        "model_mode":     "basic",
        "model":          "",
        "models": {
            "reasoning":        {"enabled": True,  "model": ""},
            "coding":           {"enabled": True,  "model": ""},
            "embedding":        {"enabled": False, "model": ""},
            "instruct":         {"enabled": True,  "model": ""},
            "function_calling": {"enabled": True,  "model": ""},
            "vision":           {"enabled": True,  "model": ""},
            "stt_tts":          {"enabled": False, "model": ""},
        },
    },
    "mcp": {"servers": {}},
    "system_modules": {
        "localai": {
            "enabled": False,
            "endpoint": "http://localhost:11434",
            "model":    "",
        },
        "backup": {
            "enabled":   False,
            "backend":   "local",
            "repo_path": "",
            "password":  "",
            "paths":     "",
            "schedule":  "manual",
        },
    },
}


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        log.debug("Config not found (returning empty): %s", path)
        return {}
    try:
        with path.open() as f:
            return yaml.safe_load(f) or {}
    except Exception:
        log.exception("Failed to load YAML: %s", path)
        return {}


def _save_yaml(path: Path, data: dict) -> None:
    log.debug("Saving YAML: %s", path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    except Exception:
        log.exception("Failed to save YAML: %s", path)
        raise


def load_global_config() -> dict:
    log.debug("Loading global config")
    data = _load_yaml(_GLOBAL_CONFIG)
    merged = _DEFAULT_CONFIG.copy()
    for section, values in data.items():
        if isinstance(values, dict) and isinstance(merged.get(section), dict):
            merged[section] = {**merged[section], **values}
        else:
            merged[section] = values
    return merged


def save_global_config(config: dict) -> None:
    log.info("Saving global config")
    _save_yaml(_GLOBAL_CONFIG, config)


def load_project_config(project_name: str) -> dict:
    log.debug("Loading project config: %s", project_name)
    path = _PROJECTS_DIR / project_name / "config.yaml"
    return _load_yaml(path)


def save_project_config(project_name: str, config: dict) -> None:
    log.info("Saving project config: %s", project_name)
    path = _PROJECTS_DIR / project_name / "config.yaml"
    _save_yaml(path, config)


def merged_mcp_servers(project_name: str | None = None) -> dict:
    log.debug("merged_mcp_servers: project=%s", project_name)
    global_cfg = load_global_config()
    servers: dict = dict(global_cfg.get("mcp", {}).get("servers", {}))

    if project_name is not None:
        project_cfg = load_project_config(project_name)
        mcp = project_cfg.get("mcp", {})
        servers.update(mcp.get("servers", {}))
        for disabled_id in mcp.get("disabled", []):
            servers.pop(disabled_id, None)

    log.debug("Effective MCP servers: %s", list(servers.keys()))
    return servers


def add_global_mcp_server(server_id: str, server_cfg: dict) -> None:
    log.info("Adding global MCP server: %s", server_id)
    config = load_global_config()
    config.setdefault("mcp", {}).setdefault("servers", {})[server_id] = server_cfg
    save_global_config(config)


def remove_global_mcp_server(server_id: str) -> None:
    log.info("Removing global MCP server: %s", server_id)
    config = load_global_config()
    config.setdefault("mcp", {}).setdefault("servers", {}).pop(server_id, None)
    save_global_config(config)


def is_ai_configured(cfg: dict | None = None) -> bool:
    """Return True if the active AI provider is fully configured."""
    if cfg is None:
        cfg = load_global_config().get("ai", {})
    provider = cfg.get("provider", "api_key")
    if provider == "api_key":
        return bool(cfg.get("api_key") or os.environ.get("ANTHROPIC_API_KEY"))
    if provider == "local":
        return bool(cfg.get("local_endpoint") and cfg.get("local_model"))
    return False
