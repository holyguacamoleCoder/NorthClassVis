"""Attach persisted run metadata to trace / timeline steps."""

from __future__ import annotations

from typing import Any

from .models import RunStatus, ToolRun
from .registry import RunRegistry


def _apply_run_to_step(step: dict[str, Any], run: ToolRun) -> dict[str, Any]:
    out = dict(step)
    out["run_id"] = run.run_id
    if run.parent_run_id:
        out["parent_run_id"] = run.parent_run_id
    if run.patch:
        out["patch"] = dict(run.patch)
    if run.derive_strategy:
        out["derive_strategy"] = run.derive_strategy
    if run.status == RunStatus.SUPERSEDED:
        out["run_status"] = "superseded"
        out["status"] = "superseded"
    elif run.status == RunStatus.CANCELLED:
        out["run_status"] = "cancelled"
        out["status"] = "cancelled"
    return out


def enrich_steps_with_runs(
    session_id: str,
    steps: list[dict[str, Any]],
    registry: RunRegistry,
    *,
    job_id: str | None = None,
) -> list[dict[str, Any]]:
    if not session_id or not steps:
        return steps

    runs = registry.list_runs(session_id, limit=100, job_id=job_id)
    by_call: dict[str, ToolRun] = {}
    for run in runs:
        if run.tool_call_id:
            by_call[str(run.tool_call_id)] = run

    # Fallback: match data tools in order when call_id missing.
    data_runs = [r for r in runs if r.tool_name in ("query_data", "aggregate_data")]
    data_idx = 0

    enriched: list[dict[str, Any]] = []
    for step in steps:
        copy = dict(step)
        call_id = str(copy.get("call_id") or "")
        run = by_call.get(call_id) if call_id else None
        if run is None and copy.get("tool") in ("query_data", "aggregate_data"):
            while data_idx < len(data_runs):
                candidate = data_runs[data_idx]
                data_idx += 1
                if candidate.tool_name == copy.get("tool"):
                    run = candidate
                    break
        if run is not None:
            copy = _apply_run_to_step(copy, run)
        enriched.append(copy)
    return enriched


def enrich_trace_and_timeline(
    session_id: str,
    payload: dict[str, Any],
    registry: RunRegistry,
    *,
    job_id: str | None = None,
) -> dict[str, Any]:
    trace = payload.get("trace") or {}
    steps = list(trace.get("steps") or [])
    enriched_steps = enrich_steps_with_runs(
        session_id,
        steps,
        registry,
        job_id=job_id,
    )
    by_call = {
        str(s["call_id"]): s
        for s in enriched_steps
        if s.get("call_id") and s.get("run_id")
    }

    timeline = payload.get("timeline") or []
    new_timeline: list[dict[str, Any]] = []
    for item in timeline:
        if item.get("kind") != "tool" or not isinstance(item.get("step"), dict):
            new_timeline.append(item)
            continue
        step = dict(item["step"])
        call_id = str(step.get("call_id") or "")
        if call_id and call_id in by_call:
            src = by_call[call_id]
            for key in ("run_id", "parent_run_id", "patch", "derive_strategy", "run_status", "status"):
                if src.get(key) is not None:
                    step[key] = src[key]
        new_item = dict(item)
        new_item["step"] = step
        new_timeline.append(new_item)

    out = dict(payload)
    out["trace"] = {"steps": enriched_steps}
    out["timeline"] = new_timeline
    return out
