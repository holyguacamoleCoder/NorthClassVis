"""HTTP-facing permission approval with blocking wait + job status updates."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable
from uuid import uuid4


class ApprovalStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._approvals: dict[str, dict[str, Any]] = {}
        self._job_id: str | None = None
        self._on_awaiting: Callable[[str, dict[str, Any]], None] | None = None

    def bind_job(self, job_id: str | None) -> None:
        with self._lock:
            self._job_id = job_id

    def set_on_awaiting(self, callback: Callable[[str, dict[str, Any]], None] | None) -> None:
        self._on_awaiting = callback

    def create_pending(
        self,
        tool_name: str,
        tool_input: dict,
        reason: str,
    ) -> str:
        approval_id = uuid4().hex
        event = threading.Event()
        payload = {
            "id": approval_id,
            "job_id": self._job_id,
            "tool_name": tool_name,
            "tool_input": dict(tool_input),
            "reason": reason,
            "created_at": time.time(),
            "event": event,
            "decision": None,
            "remember": False,
        }
        with self._lock:
            self._approvals[approval_id] = payload
        if self._on_awaiting and self._job_id:
            public = {
                "id": approval_id,
                "tool_name": tool_name,
                "tool_input": dict(tool_input),
                "reason": reason,
            }
            self._on_awaiting(self._job_id, public)
        return approval_id

    def wait_decision(self, approval_id: str, *, timeout: float = 300.0) -> tuple[bool, bool]:
        with self._lock:
            entry = self._approvals.get(approval_id)
        if entry is None:
            return False, False
        entry["event"].wait(timeout=timeout)
        with self._lock:
            entry = self._approvals.get(approval_id)
            if entry is None:
                return False, False
            decision = entry.get("decision")
            remember = bool(entry.get("remember"))
        if decision == "allow_once":
            return True, False
        if decision == "allow_always":
            return True, True
        return False, False

    def resolve(self, approval_id: str, decision: str, *, remember: bool = False) -> bool:
        with self._lock:
            entry = self._approvals.get(approval_id)
            if entry is None or entry.get("decision") is not None:
                return False
            entry["decision"] = decision
            entry["remember"] = remember
            entry["event"].set()
        return True

    def get_public(self, approval_id: str) -> dict[str, Any] | None:
        with self._lock:
            entry = self._approvals.get(approval_id)
            if entry is None:
                return None
            return {
                "id": entry["id"],
                "job_id": entry.get("job_id"),
                "tool_name": entry.get("tool_name"),
                "tool_input": entry.get("tool_input") or {},
                "reason": entry.get("reason") or "",
            }

    def cleanup(self, approval_id: str) -> None:
        with self._lock:
            self._approvals.pop(approval_id, None)

    def cancel_pending_for_job(self, job_id: str) -> int:
        """Auto-deny unresolved approvals so a cancelled job unblocks wait_decision."""
        count = 0
        with self._lock:
            for entry in self._approvals.values():
                if entry.get("job_id") != job_id or entry.get("decision") is not None:
                    continue
                entry["decision"] = "deny"
                entry["remember"] = False
                entry["event"].set()
                count += 1
        return count


class HttpApprovalHandler:
    def __init__(self, store: ApprovalStore):
        self._store = store

    def approve(
        self, tool_name: str, tool_input: dict, reason: str
    ) -> tuple[bool, bool]:
        approval_id = self._store.create_pending(tool_name, tool_input, reason)
        try:
            return self._store.wait_decision(approval_id, timeout=300.0)
        finally:
            self._store.cleanup(approval_id)
