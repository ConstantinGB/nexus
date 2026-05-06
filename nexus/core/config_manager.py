from __future__ import annotations
import copy
import os
import re
from pathlib import Path
import yaml

from nexus.core.logger import get

log = get("core.config_manager")

_ROOT = Path(__file__).parent.parent.parent
_GLOBAL_CONFIG = _ROOT / "config" / "settings.yaml"
_PROJECTS_DIR = _ROOT / "projects"

_DEFAULT_CONFIG: dict = {
    "ai": {
        # Active provider — "anthropic" | "openwebui" | "openai_compat" | "local"
        # Legacy alias "api_key" is normalised to "anthropic" on load.
        "provider": "anthropic",
        # Flat fields kept for backwards compat (read by AIClient as fallback):
        "api_key":        "",
        "local_endpoint": "http://localhost:11434",
        "local_model":    "",
        # Nested per-provider config (preferred path):
        "providers": {
            "anthropic": {
                "api_key": "",
            },
            "openwebui": {
                "base_url": "http://localhost:3000",
                "api_key":  "",
                "model":    "",
            },
            "openai_compat": {
                "base_url": "",
                "api_key":  "",
                "model":    "",
            },
            "local": {
                "endpoint": "http://localhost:11434",
                "model":    "",
            },
        },
        "model_mode":    "basic",
        "model":         "",
        "default_panel": "none",
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
    "ui": {"theme": "nexus-legacy"},
    "system_modules": {
        "localai": {
            "enabled":  False,
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
        "git": {
            "user_name":      "",
            "user_email":     "",
            "default_remote": "https",  # "https" | "ssh"
            "token":          "",
            "ssh_key_path":   "",
        },
        "home": {
            "url":   "",
            "token": "",
        },
        "sdforge": {
            "endpoint": "http://127.0.0.1:7860",
            "api_key":  "",
        },
        "server": {
            "web_root":   "",
            "http_port":  80,
            "https_port": 443,
        },
        "security": {},
        "calendar": {
            "data_path":       "",   # empty = <nexus-root>/config/calendar/
            "caldav_enabled":  False,
            "caldav_url":      "http://localhost:5232/",
            "caldav_user":     "",
            "caldav_password": "",
        },
    },
}


# ── Internal helpers ──────────────────────────────────────────────────────────

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
            yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
    except Exception:
        log.exception("Failed to save YAML: %s", path)
        raise


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base*, skipping None values."""
    result = dict(base)
    for k, v in override.items():
        if v is None:
            continue  # never let None override a non-null default
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


# ── Global config ─────────────────────────────────────────────────────────────

def load_global_config() -> dict:
    log.debug("Loading global config")
    data = _load_yaml(_GLOBAL_CONFIG)
    merged = copy.deepcopy(_DEFAULT_CONFIG)

    for section, values in data.items():
        if isinstance(values, dict) and isinstance(merged.get(section), dict):
            merged[section] = _deep_merge(merged[section], values)
        elif values is not None:
            merged[section] = values

    # Normalise legacy provider alias
    ai = merged.get("ai", {})
    if ai.get("provider") == "api_key":
        ai["provider"] = "anthropic"
    # Backfill nested providers.anthropic.api_key from flat api_key if unset
    flat_key = ai.get("api_key", "")
    if flat_key and not ai.get("providers", {}).get("anthropic", {}).get("api_key"):
        ai.setdefault("providers", {}).setdefault("anthropic", {})["api_key"] = flat_key
    # Backfill providers.local from flat local_* keys if unset
    flat_ep = ai.get("local_endpoint", "")
    flat_model = ai.get("local_model", "")
    local_p = ai.setdefault("providers", {}).setdefault("local", {})
    if flat_ep and not local_p.get("endpoint"):
        local_p["endpoint"] = flat_ep
    if flat_model and not local_p.get("model"):
        local_p["model"] = flat_model

    return merged


def save_global_config(config: dict) -> None:
    log.info("Saving global config")
    _save_yaml(_GLOBAL_CONFIG, config)


# ── Project config ────────────────────────────────────────────────────────────

def load_project_config(project_name: str) -> dict:
    log.debug("Loading project config: %s", project_name)
    path = _PROJECTS_DIR / project_name / "config.yaml"
    return _load_yaml(path)


def save_project_config(project_name: str, config: dict) -> None:
    log.info("Saving project config: %s", project_name)
    path = _PROJECTS_DIR / project_name / "config.yaml"
    _save_yaml(path, config)


# ── MCP helpers ───────────────────────────────────────────────────────────────

def mcp_servers(cfg: dict) -> dict:
    """Return the MCP servers dict from a config, always a dict (never None)."""
    return (cfg.get("mcp") or {}).get("servers") or {}


def merged_mcp_servers(project_name: str | None = None) -> dict:
    log.debug("merged_mcp_servers: project=%s", project_name)
    global_cfg = load_global_config()
    servers: dict = dict(mcp_servers(global_cfg))

    if project_name is not None:
        project_cfg = load_project_config(project_name)
        servers.update(mcp_servers(project_cfg))
        mcp = project_cfg.get("mcp") or {}
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


# ── AI helpers ────────────────────────────────────────────────────────────────

def is_ai_configured(cfg: dict | None = None) -> bool:
    """Return True if the active AI provider is fully configured."""
    if cfg is None:
        cfg = load_global_config().get("ai", {})
    provider = cfg.get("provider", "anthropic")
    if provider == "api_key":
        provider = "anthropic"

    providers_cfg = cfg.get("providers", {})

    if provider == "anthropic":
        nested_key = providers_cfg.get("anthropic", {}).get("api_key", "")
        flat_key   = cfg.get("api_key", "")
        return bool(nested_key or flat_key or os.environ.get("ANTHROPIC_API_KEY"))

    if provider in ("openwebui", "openai_compat"):
        p = providers_cfg.get(provider, {})
        return bool(p.get("base_url") and p.get("api_key"))

    if provider == "local":
        p = providers_cfg.get("local", {})
        endpoint = p.get("endpoint") or cfg.get("local_endpoint", "")
        model    = p.get("model")    or cfg.get("local_model", "")
        return bool(endpoint and model)

    return False


# ── Module mode helpers ───────────────────────────────────────────────────────

def get_module_mode(cfg: dict, module_id: str) -> str:
    """Return 'integrated' or 'standalone' for *module_id* in a project config."""
    return cfg.get("modules_config", {}).get(module_id, {}).get("mode", "integrated")


def get_system_module_global_config(module_id: str) -> dict:
    """Return the global settings block for *module_id* from config/settings.yaml."""
    return load_global_config().get("system_modules", {}).get(module_id, {})


def check_module_conflicts(module_id: str, project_config: dict) -> list[str]:
    """Return warning strings for a standalone module whose config overlaps with global."""
    warnings: list[str] = []
    global_sys = load_global_config().get("system_modules", {})
    mod_cfg    = project_config.get("modules_config", {}).get(module_id, {})

    def _port(url: str) -> str:
        m = re.search(r":(\d+)", url)
        return m.group(1) if m else ""

    if module_id == "localai":
        g_ep = global_sys.get("localai", {}).get("endpoint", "")
        s_ep = mod_cfg.get("endpoint", "")
        gp, sp = _port(g_ep), _port(s_ep)
        if gp and gp == sp:
            warnings.append(
                f"Standalone LocalAI uses port {sp}, same as the global LocalAI instance — conflict."
            )

    elif module_id == "server":
        g_srv   = global_sys.get("server", {})
        g_http  = str(g_srv.get("http_port",  80))
        g_https = str(g_srv.get("https_port", 443))
        s_http  = str(mod_cfg.get("http_port",  ""))
        s_https = str(mod_cfg.get("https_port", ""))
        if s_http  and s_http  == g_http:
            warnings.append(f"Standalone server HTTP port {s_http} conflicts with global server.")
        if s_https and s_https == g_https:
            warnings.append(f"Standalone server HTTPS port {s_https} conflicts with global server.")

    return warnings
