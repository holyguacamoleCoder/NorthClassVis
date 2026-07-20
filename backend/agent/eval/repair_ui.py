"""Backfill teacher-visible ui_messages for agent-bench sessions from scenario turns."""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from session.display import clean_user_content_for_display
from skills.message_meta import is_ui_hidden_message

_SESSION_RE = re.compile(r"^agent-bench-(.+)-r(\d+)$")


def parse_bench_session_id(session_id: str) -> tuple[str, int] | None:
    m = _SESSION_RE.match(session_id or "")
    if not m:
        return None
    return m.group(1), int(m.group(2))


def _is_turn_final_assistant(msg: dict[str, Any]) -> bool:
    """Assistant text reply with no tool_calls ≈ end of one teacher turn."""
    if msg.get("role") != "assistant":
        return False
    if msg.get("tool_calls"):
        return False
    return bool(str(msg.get("content") or "").strip())


def _copy_for_ui(msg: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(msg)
    out.pop("_agent_meta", None)
    return out


def _split_response_segments(messages: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """
    Split LLM transcript into per-turn response chunks.

    After the legacy drop_previous bug, earlier user turns are missing, so we
    cut on final assistants (content, no tool_calls) and on remaining users.
    """
    segments: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []

    def flush() -> None:
        nonlocal current
        if current:
            segments.append(current)
            current = []

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if is_ui_hidden_message(msg):
            continue
        role = msg.get("role")
        if role == "user":
            flush()
            # User markers are boundaries only; teacher text comes from fixtures.
            continue
        current.append(msg)
        if _is_turn_final_assistant(msg):
            flush()
    flush()
    return segments


def rebuild_ui_messages_from_turns(
    messages: list[dict[str, Any]],
    turns: list[str],
    *,
    ui_scope: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Rebuild durable UI transcript: scenario teacher Qs + aligned assistant/tool
    segments (even when earlier LLM user turns were dropped).
    """
    segments = _split_response_segments(list(messages or []))
    n = len(turns)

    # Align segment count to turn count: pad / merge from the end.
    if len(segments) > n:
        head = segments[: n - 1] if n else []
        tail = []
        for seg in segments[n - 1 :] if n else segments:
            tail.extend(seg)
        segments = head + ([tail] if tail else [])
    while len(segments) < n:
        segments.append([])

    ui: list[dict[str, Any]] = []
    for q, seg in zip(turns, segments):
        text = clean_user_content_for_display(q) or (q or "").strip()
        if text:
            row: dict[str, Any] = {"role": "user", "content": text}
            if ui_scope:
                row["ui_scope"] = dict(ui_scope)
            ui.append(row)
        for msg in seg:
            ui.append(_copy_for_ui(msg))
    return ui


def backfill_agent_bench_ui_messages(
    *,
    sessions_root: Path | None = None,
    scenarios_root: Path | None = None,
    only_empty: bool = True,
) -> dict[str, int]:
    """Write ui_messages.jsonl for agent-bench-* sessions from fixture turns."""
    from common.paths import SESSIONS_DIR, bootstrap_agent_paths
    from eval.schema import load_scenarios
    from session.store import FileSessionStore

    bootstrap_agent_paths()
    root = sessions_root or SESSIONS_DIR
    scen_root = scenarios_root or (
        Path(__file__).resolve().parent / "fixtures" / "scenarios"
    )
    by_id = {s.id: s for s in load_scenarios(scen_root)}
    store = FileSessionStore(root)

    stats = {"scanned": 0, "updated": 0, "skipped": 0, "missing_scenario": 0}
    for meta in store.list_meta():
        parsed = parse_bench_session_id(meta.id)
        if not parsed:
            continue
        stats["scanned"] += 1
        scenario_id, _run = parsed
        scenario = by_id.get(scenario_id)
        if scenario is None:
            stats["missing_scenario"] += 1
            continue
        session = store.load(meta.id)
        if session is None:
            stats["skipped"] += 1
            continue
        if only_empty and session.ui_messages:
            stats["skipped"] += 1
            continue
        session.ui_messages = rebuild_ui_messages_from_turns(
            list(session.messages or []),
            list(scenario.turns),
            ui_scope=scenario.ui_scope or None,
        )
        session.user_turn_count = len(scenario.turns)
        session.messages_count = len(session.messages or [])
        store.save(session)
        stats["updated"] += 1
    return stats
