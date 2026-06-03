"""Tool run domain model (one query_data / aggregate_data execution)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class RunStatus(str, Enum):
    QUEUED = "queued"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


TERMINAL_RUN_STATUSES = frozenset({
    RunStatus.COMPLETED,
    RunStatus.FAILED,
    RunStatus.CANCELLED,
    RunStatus.SUPERSEDED,
})

DATA_RUN_TOOLS = frozenset({"query_data", "aggregate_data"})


@dataclass
class ToolRun:
    run_id: str
    session_id: str
    tool_name: str
    status: RunStatus = RunStatus.QUEUED
    params: dict[str, Any] = field(default_factory=dict)

    job_id: str | None = None
    tool_call_id: str | None = None
    user_turn: int = 0

    result_ref: str | None = None
    dataset_id: str | None = None
    error: str | None = None

    parent_run_id: str | None = None
    superseded_by: str | None = None
    patch: dict[str, Any] | None = None
    derive_strategy: str | None = None

    created_at: float = 0.0
    started_at: float | None = None
    finished_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolRun:
        status_raw = data.get("status", RunStatus.QUEUED.value)
        try:
            status = RunStatus(str(status_raw))
        except ValueError:
            status = RunStatus.QUEUED
        return cls(
            run_id=str(data["run_id"]),
            session_id=str(data["session_id"]),
            tool_name=str(data["tool_name"]),
            status=status,
            params=dict(data.get("params") or {}),
            job_id=data.get("job_id"),
            tool_call_id=data.get("tool_call_id"),
            user_turn=int(data.get("user_turn") or 0),
            result_ref=data.get("result_ref"),
            dataset_id=data.get("dataset_id"),
            error=data.get("error"),
            parent_run_id=data.get("parent_run_id"),
            superseded_by=data.get("superseded_by"),
            patch=dict(data.get("patch") or {}) if data.get("patch") else None,
            derive_strategy=data.get("derive_strategy"),
            created_at=float(data.get("created_at") or 0),
            started_at=float(data["started_at"]) if data.get("started_at") is not None else None,
            finished_at=float(data["finished_at"]) if data.get("finished_at") is not None else None,
        )
