"""Persist and coordinate tool run lifecycle per session."""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from common.paths import AGENT_STATE_DIR

from .derive import DerivePlan, plan_derive
from .models import DATA_RUN_TOOLS, TERMINAL_RUN_STATUSES, RunStatus, ToolRun


def _runs_path(session_id: str) -> Path:
    return AGENT_STATE_DIR / "sessions" / session_id / "runs.jsonl"


class RunRegistry:
    """Session-scoped tool run registry with in-memory cancel coordination."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cancel_requested: set[str] = set()
        self._active_run_by_job: dict[str, str] = {}

    def begin_run(
        self,
        *,
        session_id: str,
        tool_name: str,
        params: dict[str, Any],
        job_id: str | None = None,
        tool_call_id: str | None = None,
        user_turn: int = 0,
        parent_run_id: str | None = None,
        patch: dict[str, Any] | None = None,
        derive_strategy: str | None = None,
    ) -> str:
        if tool_name not in DATA_RUN_TOOLS:
            raise ValueError(f"unsupported tool for run registry: {tool_name}")

        run_id = uuid.uuid4().hex[:12]
        now = time.time()
        run = ToolRun(
            run_id=run_id,
            session_id=session_id,
            tool_name=tool_name,
            status=RunStatus.EXECUTING,
            params={k: v for k, v in params.items() if not str(k).startswith("_")},
            job_id=job_id,
            tool_call_id=tool_call_id,
            user_turn=user_turn,
            parent_run_id=parent_run_id,
            patch=patch,
            derive_strategy=derive_strategy,
            created_at=now,
            started_at=now,
        )
        self._append_run(session_id, run)
        with self._lock:
            if job_id:
                self._active_run_by_job[job_id] = run_id
        return run_id

    def complete_run(
        self,
        run_id: str,
        *,
        result_ref: str | None = None,
        dataset_id: str | None = None,
    ) -> None:
        run = self.get_run(run_id)
        if run is None:
            return
        if run.status in (RunStatus.SUPERSEDED, RunStatus.CANCELLED):
            return
        if run.status == RunStatus.CANCELLING:
            self.finalize_cancelled(run_id)
            return
        self._update_run(
            run,
            status=RunStatus.COMPLETED,
            result_ref=result_ref,
            dataset_id=dataset_id,
            finished_at=time.time(),
        )
        self._clear_active(run)

    def fail_run(self, run_id: str, error: str) -> None:
        run = self.get_run(run_id)
        if run is None:
            return
        if run.status in (RunStatus.SUPERSEDED, RunStatus.CANCELLED, RunStatus.CANCELLING):
            if run.status == RunStatus.CANCELLING:
                self.finalize_cancelled(run_id)
            return
        self._update_run(
            run,
            status=RunStatus.FAILED,
            error=error[:500],
            finished_at=time.time(),
        )
        self._clear_active(run)

    def cancel_run(self, run_id: str, *, reason: str = "user_cancel") -> bool:
        run = self.get_run(run_id)
        if run is None:
            return False
        if run.status in TERMINAL_RUN_STATUSES:
            return False
        with self._lock:
            self._cancel_requested.add(run_id)
        status = RunStatus.CANCELLED if run.status == RunStatus.QUEUED else RunStatus.CANCELLING
        self._update_run(
            run,
            status=status,
            error=reason if status == RunStatus.CANCELLED else run.error,
            finished_at=time.time() if status == RunStatus.CANCELLED else None,
        )
        if status == RunStatus.CANCELLED:
            self._clear_active(run)
        return True

    def finalize_cancelled(self, run_id: str) -> None:
        run = self.get_run(run_id)
        if run is None:
            return
        self._update_run(
            run,
            status=RunStatus.CANCELLED,
            finished_at=time.time(),
        )
        with self._lock:
            self._cancel_requested.discard(run_id)
        self._clear_active(run)

    def mark_superseded(self, parent_run_id: str, child_run_id: str) -> None:
        parent = self.get_run(parent_run_id)
        if parent is None:
            return
        if parent.status == RunStatus.EXECUTING:
            self.cancel_run(parent_run_id, reason="superseded")
        self._update_run(
            parent,
            status=RunStatus.SUPERSEDED,
            superseded_by=child_run_id,
            finished_at=parent.finished_at or time.time(),
        )

    def should_cancel_run(self, run_id: str) -> bool:
        with self._lock:
            if run_id in self._cancel_requested:
                return True
        run = self.get_run(run_id)
        return run is not None and run.status in (RunStatus.CANCELLING, RunStatus.CANCELLED)

    def request_cancel_for_job(self, job_id: str) -> int:
        count = 0
        with self._lock:
            active_run_id = self._active_run_by_job.get(job_id)
        if active_run_id and self.cancel_run(active_run_id):
            count += 1
        return count

    def derive_run(
        self,
        parent_run_id: str,
        patch: dict[str, Any],
    ) -> DerivePlan | None:
        parent = self.get_run(parent_run_id)
        if parent is None:
            return None
        return plan_derive(parent, patch, registry=self)

    def get_run(self, run_id: str) -> ToolRun | None:
        for path in (AGENT_STATE_DIR / "sessions").glob("*/runs.jsonl"):
            for run in self._read_runs_file(path):
                if run.run_id == run_id:
                    return run
        return None

    def list_runs(
        self,
        session_id: str,
        *,
        limit: int = 30,
        job_id: str | None = None,
    ) -> list[ToolRun]:
        path = _runs_path(session_id)
        runs = self._read_runs_file(path)
        if job_id:
            runs = [r for r in runs if r.job_id == job_id]
        return runs[-limit:]

    def recent_modifiable_runs(self, session_id: str, *, limit: int = 10) -> list[ToolRun]:
        runs = self.list_runs(session_id, limit=limit * 3)
        out: list[ToolRun] = []
        for run in reversed(runs):
            if run.tool_name not in DATA_RUN_TOOLS:
                continue
            if run.superseded_by:
                continue
            if run.status in (RunStatus.SUPERSEDED, RunStatus.CANCELLED, RunStatus.FAILED):
                continue
            out.append(run)
            if len(out) >= limit:
                break
        out.reverse()
        return out

    def _clear_active(self, run: ToolRun) -> None:
        if not run.job_id:
            return
        with self._lock:
            if self._active_run_by_job.get(run.job_id) == run.run_id:
                del self._active_run_by_job[run.job_id]

    def _append_run(self, session_id: str, run: ToolRun) -> None:
        path = _runs_path(session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(run.to_dict(), ensure_ascii=False, default=str) + "\n")

    def _read_runs_file(self, path: Path) -> list[ToolRun]:
        if not path.is_file():
            return []
        by_id: dict[str, ToolRun] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                run = ToolRun.from_dict(data)
                by_id[run.run_id] = run
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
        return list(by_id.values())

    def _update_run(self, run: ToolRun, **updates: Any) -> None:
        path = _runs_path(run.session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        merged = ToolRun.from_dict({**run.to_dict(), **updates})
        if isinstance(updates.get("status"), RunStatus):
            merged.status = updates["status"]
        elif "status" in updates:
            merged.status = RunStatus(str(updates["status"]))
        for key, value in updates.items():
            if key == "status":
                continue
            setattr(merged, key, value)
        self._append_run(run.session_id, merged)
