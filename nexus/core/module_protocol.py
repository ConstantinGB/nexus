from __future__ import annotations
from typing import Protocol, runtime_checkable


@runtime_checkable
class ModuleScreen(Protocol):
    """Rendering-framework-independent contract for a project screen.

    Both the Textual TUI BaseProjectScreen and the future PySide6
    BaseProjectWindow implement this protocol, allowing core logic to
    interact with either without importing framework-specific code.
    """

    def get_config(self) -> dict: ...
    def save_config(self, data: dict) -> None: ...
    def list_actions(self) -> list[str]: ...
    async def handle_action(self, action_id: str) -> str: ...
    async def populate_content(self) -> None: ...
