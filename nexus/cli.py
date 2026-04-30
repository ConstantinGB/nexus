"""Headless CLI commands for Nexus (no TUI required)."""
from __future__ import annotations


def cmd_list() -> None:
    from nexus.core.project_manager import list_projects

    projects = list_projects()
    if not projects:
        print("No projects found. Run 'nexus' to create one.")
        return

    # Column widths
    w_name   = max(len("NAME"),   max(len(p.name)   for p in projects))
    w_module = max(len("MODULE"), max(len(p.module) for p in projects))
    w_desc   = max(len("DESCRIPTION"), max(len(p.description or "") for p in projects), 1)

    sep  = f"+{'-' * (w_name + 2)}+{'-' * (w_module + 2)}+{'-' * (w_desc + 2)}+"
    row  = lambda n, m, d: f"| {n:<{w_name}} | {m:<{w_module}} | {d:<{w_desc}} |"

    print(sep)
    print(row("NAME", "MODULE", "DESCRIPTION"))
    print(sep)
    for p in projects:
        print(row(p.name, p.module, p.description or ""))
    print(sep)
    print(f"\n{len(projects)} project(s)")


def cmd_version() -> None:
    try:
        from importlib.metadata import version
        v = version("nexus")
    except Exception:
        v = "unknown"
    print(f"nexus {v}")
