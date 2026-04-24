from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Any


@dataclass
class Flow:
    """A declared data pathway between two module types.

    Examples:
        Flow("research", "codex",   "summarize_to_codex",  "Distill research findings into a Codex entry")
        Flow("git",      "journal", "summarize_to_journal", "Summarize recent commits into a journal entry")
        Flow("research", "org",     "outline_to_org",       "Turn research notes into an org plan")
    """
    source: str        # module type id (e.g. "research")
    target: str        # module type id (e.g. "codex")
    action: str        # short identifier for the operation
    description: str   # human-readable description shown in the UI


class Mycelium:
    """Inter-module communication bus.

    Mycelium knows which modules exist, how they relate to each other,
    and how data should flow between them. It is the connective tissue
    that lets the AI orchestrate multi-module workflows without each
    module having to know about the others.

    Responsibilities:
    - Register active project instances by module type
    - Declare and store inter-module Flows
    - Route messages/payloads from a source module to a target module
    - Provide the AI with a map of available flows so it can suggest
      or execute cross-module actions (e.g. "summarize research → codex")
    """

    def __init__(self) -> None:
        self._flows: list[Flow] = []
        self._handlers: dict[str, Callable[[Any], Any]] = {}  # action -> handler fn
        self._instances: dict[str, list[str]] = {}            # module_type -> [project_names]

    # -- Flow registration --------------------------------------------------

    def register_flow(self, flow: Flow) -> None:
        self._flows.append(flow)

    def register_handler(self, action: str, fn: Callable[[Any], Any]) -> None:
        self._handlers[action] = fn

    # -- Instance registry --------------------------------------------------

    def register_instance(self, module_type: str, project_name: str) -> None:
        self._instances.setdefault(module_type, []).append(project_name)

    def instances_of(self, module_type: str) -> list[str]:
        return self._instances.get(module_type, [])

    # -- Querying -----------------------------------------------------------

    def flows_from(self, source: str) -> list[Flow]:
        return [f for f in self._flows if f.source == source]

    def flows_to(self, target: str) -> list[Flow]:
        return [f for f in self._flows if f.target == target]

    def all_flows(self) -> list[Flow]:
        return list(self._flows)

    # -- Execution ----------------------------------------------------------

    async def send(self, action: str, payload: Any) -> Any:
        handler = self._handlers.get(action)
        if handler is None:
            raise NotImplementedError(f"No handler registered for action {action!r}")
        return await handler(payload)


# Default flows wired up at app startup
DEFAULT_FLOWS: list[Flow] = [
    Flow("research", "codex",   "research_to_codex",   "Summarize research findings into a Codex knowledge entry"),
    Flow("git",      "journal", "git_to_journal",      "Summarize recent commits and progress into a journal entry"),
    Flow("research", "org",     "research_to_org",     "Turn research notes into an org plan or outline"),
    Flow("codex",    "journal", "codex_to_journal",    "Write a journal entry reflecting on a Codex topic"),
    Flow("org",      "journal", "org_to_journal",      "Log completed org tasks or milestones to the journal"),
]
