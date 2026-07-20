"""Per-turn agent hints (prefix-cache safe; no history rewrite)."""

from __future__ import annotations

import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import runtime_bootstrap  # noqa: F401, E402

from data.filter_context import FilterContext  # noqa: E402
from hints.report_continue import format_report_continue_hint  # noqa: E402
from session.turn_hints import build_turn_agent_hint  # noqa: E402
from session.ui_scope import compose_llm_user_content  # noqa: E402


def test_build_turn_hint_includes_modify_and_todo():
    messages = [{"role": "user", "content": "旧问题"}]
    hint = build_turn_agent_hint(
        modify_context={
            "parent_run_id": "r1",
            "strategy": "requery",
            "patch": {},
        },
        todo_items=[{"content": "query Class1", "status": "in_progress"}],
    )
    assert hint is not None
    assert "r1" in hint
    assert "query Class1" in hint
    assert messages[0]["content"] == "旧问题"


def test_report_continue_is_hint_not_rewrite():
    msgs = [{"role": "user", "content": "继续写报告"}]
    hint = format_report_continue_hint("reports/class/Class1/overview.md")
    assert "reports/class/Class1/overview.md" in hint
    assert "<reminder>" in hint
    assert msgs[0]["content"] == "继续写报告"


def test_compose_merges_turn_hint_once():
    hint = build_turn_agent_hint(
        filter_context=FilterContext(classes=("Class1",), source="http_body"),
        teacher_message="继续完成报告",
        report_continue_path="reports/x.md",
    )
    merged = compose_llm_user_content("继续完成报告", hint)
    assert merged.startswith("[系统") or "本轮" in merged or "<reminder>" in merged
    assert merged.count("<reminder>") == 1
    assert "教师本轮问题" in merged or "继续完成报告" in merged
