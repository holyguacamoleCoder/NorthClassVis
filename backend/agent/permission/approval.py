from __future__ import annotations

import json
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .manager import PermissionManager


class ApprovalHandler(Protocol):
    def approve(
        self, tool_name: str, tool_input: dict, reason: str
    ) -> bool | tuple[bool, bool]:
        """
        Return True to allow once, or (allowed, remember_permanently).
        """


class DenyAskApprovalHandler:
    """Headless / API: never approve interactive asks."""

    def approve(
        self, tool_name: str, tool_input: dict, reason: str
    ) -> tuple[bool, bool]:
        return False, False


class CliApprovalHandler:
    def __init__(self, manager: PermissionManager | None = None):
        self._manager = manager

    def bind(self, manager: PermissionManager) -> None:
        self._manager = manager

    def approve(
        self, tool_name: str, tool_input: dict, reason: str
    ) -> tuple[bool, bool]:
        preview = json.dumps(tool_input, ensure_ascii=False)[:200]
        print(f"\n  [Permission] {reason}")
        print(f"  {tool_name}: {preview}")
        try:
            answer = input("  Allow? (y/n/always): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False, False
        if answer == "always":
            return True, True
        if answer in ("y", "yes"):
            return True, False
        return False, False


class CallbackApprovalHandler:
    def __init__(self, callback):
        self._callback = callback

    def approve(
        self, tool_name: str, tool_input: dict, reason: str
    ) -> bool | tuple[bool, bool]:
        return bool(self._callback(tool_name, tool_input, reason))
