"""Persist per-turn UI trace (tool steps / timeline) separately from LLM messages."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .turns import count_user_turns

TURN_TRACES_FILE = "turn_traces.jsonl"

# Fields needed to rebuild assistant bubbles on session reload.
_TURN_TRACE_UI_KEYS = (
    "thinking",
    "thinking_updates",
    "answer",
    "closing",
    "trace",
    "timeline",
    "visual_links",
    "report_links",
    "report_evidence",
    "memory_saved",
    "goal_check",
    "summary",
    "continue_reason",
    "report_final_check",
    "evidence",
    "actions",
)


def turn_traces_path(session_dir: Path) -> Path:
    return session_dir / TURN_TRACES_FILE


def _extract_ui_payload(result: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in _TURN_TRACE_UI_KEYS:
        if key in result and result[key] is not None:
            out[key] = result[key]
    return out


def _merge_progress_into_result(
    result: dict[str, Any],
    progress: dict[str, Any] | None,
) -> dict[str, Any]:
    """Prefer streaming progress for trace/timeline (subagent inner_steps, etc.)."""
    if not progress:
        return result
    merged = dict(result)
    timeline = progress.get("timeline")
    if isinstance(timeline, list) and timeline:
        merged["timeline"] = timeline
    tool_steps = progress.get("tool_steps")
    if isinstance(tool_steps, list) and tool_steps:
        merged["trace"] = {"steps": tool_steps}
    if progress.get("memory_saved"):
        merged["memory_saved"] = list(progress["memory_saved"])
    if progress.get("report_links") and not merged.get("report_links"):
        merged["report_links"] = list(progress["report_links"])
    return merged


def _last_user_preview(messages: list[dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return str(msg.get("content") or "")[:240]
    return ""


def build_turn_trace_record(
    *,
    session_id: str,
    messages: list[dict[str, Any]],
    result: dict[str, Any],
    progress: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged = _merge_progress_into_result(result, progress)
    ui = _extract_ui_payload(merged)
    return {
        "turn_index": count_user_turns(messages),
        "session_id": session_id,
        "recorded_at": time.time(),
        "user_preview": _last_user_preview(messages),
        **ui,
    }


def load_turn_traces(session_dir: Path) -> list[dict[str, Any]]:
    path = turn_traces_path(session_dir)
    if not path.is_file():
        return []
    by_turn: dict[int, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        turn_index = int(row.get("turn_index") or 0)
        if turn_index > 0:
            by_turn[turn_index] = row
    return [by_turn[k] for k in sorted(by_turn)]


def append_turn_trace(session_dir: Path, record: dict[str, Any]) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    path = turn_traces_path(session_dir)
    turn_index = int(record.get("turn_index") or 0)
    existing = load_turn_traces(session_dir)
    if existing and int(existing[-1].get("turn_index") or 0) == turn_index:
        lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
        if lines:
            lines[-1] = json.dumps(record, ensure_ascii=False)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def turn_trace_for_index(
    traces: list[dict[str, Any]],
    turn_index: int,
) -> dict[str, Any] | None:
    for row in traces:
        if int(row.get("turn_index") or 0) == turn_index:
            return row
    return None
