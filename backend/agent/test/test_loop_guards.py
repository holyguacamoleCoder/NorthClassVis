"""Tests for loop turn limits and report validate loop guards."""

from __future__ import annotations

from collections import deque

import runtime_bootstrap  # noqa: F401, E402

from hints.report_validate_guard import (
    collect_report_tool_signatures,
    report_validate_blocker_signature,
    report_validate_soft_signature,
)
from loop import AgentLoop
from loop_limits import REPORT_POLISH_LOOP_WINDOW, REPORT_VALIDATE_LOOP_WINDOW
from loop_state import LoopState


def test_blocker_signature_detects_fail_status():
    content = (
        "[Edit OK]\n\nError: Report validation failed.\n\n"
        "[Report validate]\nstatus: fail\n  error: bad chart json"
    )
    assert report_validate_blocker_signature(content) == "blocker:bad chart json"


def test_soft_signature_detects_warn_only():
    content = (
        "[Edit OK]\n\n[Report validate]\nstatus: warn\n"
        "  warn: total lines 51 < tier minimum 70"
    )
    assert report_validate_soft_signature(content).startswith("warn:")


def test_collect_signatures_from_write_tools_only():
    calls = [
        {"id": "c1", "name": "edit_file"},
        {"id": "c2", "name": "query_data"},
    ]
    results = [
        {
            "tool_call_id": "c1",
            "content": "[Edit OK]\n\n[Report validate]\nstatus: warn\n  warn: x",
        },
        {"tool_call_id": "c2", "content": "ok",
        },
    ]
    sigs = collect_report_tool_signatures(calls, results)
    assert len(sigs) == 1
    assert sigs[0].startswith("warn:")


def test_report_validate_loop_guard_triggers_on_repeated_blocker():
    loop = AgentLoop(LoopState(messages=[]))
    loop._recent_report_blocker_signatures = deque(maxlen=REPORT_VALIDATE_LOOP_WINDOW)
    calls = [{"id": "c1", "name": "edit_file"}]
    blocker = (
        "[Edit OK]\n\nError: Report validation failed.\n\n"
        "[Report validate]\nstatus: fail\n  error: same issue"
    )
    for _ in range(REPORT_VALIDATE_LOOP_WINDOW):
        reason = loop._check_report_validate_loop_guard(
            calls,
            [{"tool_call_id": "c1", "content": blocker}],
        )
    assert reason == "report_validate_loop_guard"


def test_report_polish_loop_guard_triggers_on_repeated_warn():
    loop = AgentLoop(LoopState(messages=[]))
    loop._recent_report_soft_signatures = deque(maxlen=REPORT_POLISH_LOOP_WINDOW)
    calls = [{"id": "c1", "name": "edit_file"}]
    warn = "[Edit OK]\n\n[Report validate]\nstatus: warn\n  warn: lines low"
    reason = None
    for _ in range(REPORT_POLISH_LOOP_WINDOW):
        reason = loop._check_report_validate_loop_guard(
            calls,
            [{"tool_call_id": "c1", "content": warn}],
        )
    assert reason == "report_polish_loop_guard"
