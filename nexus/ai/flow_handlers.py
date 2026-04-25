from __future__ import annotations
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path

from nexus.core.config_manager import load_global_config, load_project_config, is_ai_configured
from nexus.core.logger import get
from nexus.core.project_manager import list_projects, _PROJECTS_DIR

log = get("flow_handlers")


# ── Shared helpers ────────────────────────────────────────────────────────────

def _first_project_of(module: str) -> str | None:
    projects = [p for p in list_projects() if p.module == module]
    return projects[0].slug if projects else None


async def _ai_synthesize(prompt: str, system: str) -> str | None:
    if not is_ai_configured():
        return None
    try:
        from nexus.ai.client import AIClient
        return await AIClient().chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=system,
            skill_scopes=[],
        )
    except Exception:
        log.exception("AI synthesis failed in flow handler")
        return None


def _get_configured_dir(cfg: dict, module_key: str, dir_key: str, slug: str) -> Path:
    p = Path(cfg.get(module_key, {}).get(dir_key, "")).expanduser()
    if not str(p) or p == Path("."):
        raise ValueError(f"{module_key.title()} directory not configured for project '{slug}'")
    return p


def _resolve_research_note(notes_dir: Path, note_filename: str | None) -> Path | None:
    if note_filename:
        return notes_dir / note_filename
    return max(notes_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, default=None)


# ── Write helpers ─────────────────────────────────────────────────────────────

_JOURNAL_TEX = r"""\documentclass[12pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{parskip}
\author{%(author)s}
\title{%(title)s}
\date{%(date)s}
\begin{document}
\maketitle
%(content)s
\end{document}
"""


def _write_journal_entry(slug: str, title: str, content: str) -> Path:
    cfg = load_project_config(slug)
    journal_dir = _get_configured_dir(cfg, "journal", "journal_dir", slug)
    author = cfg.get("journal", {}).get("author", "")
    now = datetime.now()
    entry_dir = journal_dir / "entries" / now.strftime("%Y")
    entry_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-z0-9]+", "-", title.lower())[:40].strip("-")
    path = entry_dir / f"{now.strftime('%Y-%m-%d')}-{safe}.tex"
    path.write_text(_JOURNAL_TEX % {
        "author": author,
        "title": title,
        "date": now.strftime("%Y-%m-%d"),
        "content": content,
    })
    return path


def _write_codex_entry(slug: str, title: str, content: str) -> Path:
    cfg = load_project_config(slug)
    vault_dir = _get_configured_dir(cfg, "codex", "vault_dir", slug)
    vault_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    date_id = now.strftime("%Y%m%d%H%M%S")
    slug_name = re.sub(r"[^a-z0-9]+", "-", title.lower())[:50].strip("-")
    text = (
        f"---\nid: {date_id}\ntitle: {title}\n"
        f"date: {now.strftime('%Y-%m-%d')}\ntags: []\nlinks: []\n---\n\n"
        f"# {title}\n\n{content}\n"
    )
    path = vault_dir / f"{date_id}-{slug_name}.md"
    path.write_text(text)
    return path


def _write_org_plan(slug: str, name: str, content: str) -> Path:
    cfg = load_project_config(slug)
    output_dir = _get_configured_dir(cfg, "org", "output_dir", slug)
    output_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    filename = re.sub(r"[^a-z0-9]+", "-", name.lower())[:50].strip("-") + ".md"
    path = output_dir / filename
    path.write_text(f"# {name}\n\n_Created: {now.strftime('%Y-%m-%d')}_\n\n{content}\n")
    return path


# ── Flow handlers ─────────────────────────────────────────────────────────────

async def _git_to_journal(payload: dict) -> str:
    source_slug = payload.get("source_slug") or _first_project_of("git")
    target_slug = payload.get("target_slug") or _first_project_of("journal")

    if not source_slug:
        return json.dumps({"error": "No git project found."})
    if not target_slug:
        return json.dumps({"error": "No journal project found."})

    git_cfg = load_project_config(source_slug).get("git", {})
    repo_filter = payload.get("repo")
    repos_to_scan = (
        [r["name"] for r in git_cfg.get("repos", []) if r["name"] == repo_filter]
        if repo_filter
        else [r["name"] for r in git_cfg.get("repos", [])]
    )
    n = int(payload.get("n", 20))

    from modules.git.git_ops import get_recent_commits

    async def _fetch(repo_name: str) -> list[str]:
        repo_path = _PROJECTS_DIR / source_slug / "repos" / repo_name
        if not repo_path.exists():
            return []
        commits = await asyncio.to_thread(get_recent_commits, repo_path, n)
        return [f"[{repo_name}] {c['date'][:10]} {c['hash'][:7]} {c['message']}" for c in commits]

    results = await asyncio.gather(*[_fetch(r) for r in repos_to_scan])
    all_lines = [line for sublist in results for line in sublist]

    if not all_lines:
        return json.dumps({"error": "No commits found in the git project."})

    commit_text = "\n".join(all_lines)
    body = await _ai_synthesize(
        f"Write a concise developer journal entry (3-6 sentences) reflecting on these recent commits. Be personal and reflective, not just a list.\n\nCommits:\n{commit_text}",
        "You summarise a developer's recent git activity into a short, reflective journal entry.",
    ) or "Recent commits:\n\n" + "\n".join(f"- {l}" for l in all_lines)

    try:
        path = await asyncio.to_thread(_write_journal_entry, target_slug, "Git Activity", body)
    except Exception as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"success": True, "path": str(path)})


async def _research_to_codex(payload: dict) -> str:
    source_slug = payload.get("source_slug") or _first_project_of("research")
    target_slug = payload.get("target_slug") or _first_project_of("codex")

    if not source_slug:
        return json.dumps({"error": "No research project found."})
    if not target_slug:
        return json.dumps({"error": "No codex project found."})

    notes_dir = Path(
        load_project_config(source_slug).get("research", {}).get("notes_dir", "")
    ).expanduser()

    note_path = await asyncio.to_thread(_resolve_research_note, notes_dir, payload.get("note_filename"))
    if not note_path:
        return json.dumps({"error": "No research notes found."})
    if not await asyncio.to_thread(note_path.exists):
        return json.dumps({"error": f"Note not found: {note_path.name}"})

    note_content = await asyncio.to_thread(note_path.read_text, errors="replace")
    title = note_path.stem.replace("-", " ").title()

    body = await _ai_synthesize(
        f"Distil this research note into a concise Zettelkasten entry. Extract the core insight in 2-4 paragraphs. Remove raw URLs or data, synthesise ideas instead.\n\n{note_content}",
        "You are a knowledge manager who turns research notes into permanent Zettelkasten entries.",
    ) or note_content

    try:
        path = await asyncio.to_thread(_write_codex_entry, target_slug, title, body)
    except Exception as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"success": True, "path": str(path), "title": title})


async def _research_to_org(payload: dict) -> str:
    source_slug = payload.get("source_slug") or _first_project_of("research")
    target_slug = payload.get("target_slug") or _first_project_of("org")

    if not source_slug:
        return json.dumps({"error": "No research project found."})
    if not target_slug:
        return json.dumps({"error": "No org project found."})

    notes_dir = Path(
        load_project_config(source_slug).get("research", {}).get("notes_dir", "")
    ).expanduser()

    note_path = await asyncio.to_thread(_resolve_research_note, notes_dir, payload.get("note_filename"))
    if not note_path:
        return json.dumps({"error": "No research notes found."})
    if not await asyncio.to_thread(note_path.exists):
        return json.dumps({"error": f"Note not found: {note_path.name}"})

    note_content = await asyncio.to_thread(note_path.read_text, errors="replace")
    plan_name = payload.get("plan_name") or note_path.stem.replace("-", " ").title()

    body = await _ai_synthesize(
        f"Turn this research note into an actionable plan. List 5-10 concrete next steps as a Markdown task list (- [ ] item). Then add a short 'Background' section summarising the research.\n\n{note_content}",
        "You are a project planner who turns research notes into concrete action plans.",
    ) or (
        f"## Tasks\n\n- [ ] Review: {note_path.name}\n\n"
        f"## Background\n\n{note_content[:500]}"
    )

    try:
        path = await asyncio.to_thread(_write_org_plan, target_slug, plan_name, body)
    except Exception as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"success": True, "path": str(path), "plan": plan_name})


async def _codex_to_journal(payload: dict) -> str:
    source_slug = payload.get("source_slug") or _first_project_of("codex")
    target_slug = payload.get("target_slug") or _first_project_of("journal")

    if not source_slug:
        return json.dumps({"error": "No codex project found."})
    if not target_slug:
        return json.dumps({"error": "No journal project found."})

    vault_dir = Path(
        load_project_config(source_slug).get("codex", {}).get("vault_dir", "")
    ).expanduser()

    entry_id = payload.get("entry_id")
    if entry_id:
        matches = await asyncio.to_thread(lambda: list(vault_dir.glob(f"{entry_id}*.md")))
        entry_path = matches[0] if matches else None
    else:
        entry_path = await asyncio.to_thread(
            lambda: max(vault_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, default=None)
        )

    if not entry_path:
        return json.dumps({"error": "No codex entry found."})

    entry_content = await asyncio.to_thread(entry_path.read_text, errors="replace")
    parts = entry_path.stem.split("-", 1)
    topic = parts[-1].replace("-", " ").title() if len(parts) > 1 else entry_path.stem

    body = await _ai_synthesize(
        f"Write a personal journal entry (3-6 sentences) reflecting on this knowledge entry. How does it connect to your work or thinking? What questions does it raise?\n\n{entry_content}",
        "You help a developer write personal journal reflections based on their knowledge base entries.",
    ) or f"Reflecting on: {topic}\n\n{entry_content[:600]}"

    try:
        path = await asyncio.to_thread(_write_journal_entry, target_slug, f"Reflection: {topic}", body)
    except Exception as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"success": True, "path": str(path)})


async def _org_to_journal(payload: dict) -> str:
    source_slug = payload.get("source_slug") or _first_project_of("org")
    target_slug = payload.get("target_slug") or _first_project_of("journal")

    if not source_slug:
        return json.dumps({"error": "No org project found."})
    if not target_slug:
        return json.dumps({"error": "No journal project found."})

    output_dir = Path(
        load_project_config(source_slug).get("org", {}).get("output_dir", "")
    ).expanduser()

    plan_name = payload.get("plan_name")
    if plan_name:
        safe = re.sub(r"[^a-z0-9]+", "-", plan_name.lower())
        matches = await asyncio.to_thread(lambda: list(output_dir.glob(f"*{safe}*.md")))
        plan_path = matches[0] if matches else None
    else:
        plan_path = await asyncio.to_thread(
            lambda: max(output_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, default=None)
        )

    if not plan_path:
        return json.dumps({"error": "No org plan found."})

    plan_content = await asyncio.to_thread(plan_path.read_text, errors="replace")
    plan_title = plan_path.stem.replace("-", " ").title()

    body = await _ai_synthesize(
        f"Write a brief journal log entry (3-5 sentences) recording progress or completion of this plan. Note what was accomplished and what comes next.\n\n{plan_content}",
        "You help a developer log their planning and task progress into a personal journal.",
    ) or f"Plan log: {plan_title}\n\n{plan_content[:600]}"

    try:
        path = await asyncio.to_thread(_write_journal_entry, target_slug, f"Plan Log: {plan_title}", body)
    except Exception as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"success": True, "path": str(path)})


# ── Registration ──────────────────────────────────────────────────────────────

def register_flow_handlers() -> None:
    from nexus.core.mycelium import bus
    bus.register_handler("git_to_journal",    _git_to_journal)
    bus.register_handler("research_to_codex", _research_to_codex)
    bus.register_handler("research_to_org",   _research_to_org)
    bus.register_handler("codex_to_journal",  _codex_to_journal)
    bus.register_handler("org_to_journal",    _org_to_journal)
    log.info("Mycelium: 5 flow handlers registered")
