"""Turn stop summary when hitting max turns or loop guards."""

from __future__ import annotations

import runtime_bootstrap  # noqa: F401, E402

from hints.turn_stop_summary import build_turn_stop_summary
from loop import AgentLoop
from loop_limits import MAX_TURNS_PER_USER_ROUND
from loop_state import LoopState


def test_build_turn_stop_summary_includes_errors_and_report():
    messages = [
        {"role": "user", "content": "Class2 第 13-15 周班级学情总览"},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "q1",
                    "function": {
                        "name": "query_data",
                        "arguments": '{"resource":"week_aggregation","classes":["Class2"]}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "q1",
            "content": '[Summary] resource=week_aggregation, rows_scanned=255\n\n{"meta":{"rows_scanned":255}}',
        },
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "a1",
                    "function": {
                        "name": "aggregate_data",
                        "arguments": '{"input":{"result_ref":"query-results/x.json"}}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "a1",
            "content": "Error: 绑定 scope=class_wide 但 ds_x 仅为 255 行。",
        },
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "w1",
                    "function": {
                        "name": "write_file",
                        "arguments": '{"path":"reports/class/Class2/overview.md"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "w1",
            "content": "[Write OK: path=reports/class/Class2/overview.md, bytes=100]",
        },
    ]
    text = build_turn_stop_summary(
        messages,
        reason_title="轮次上限停止摘要",
        turns_used=12,
        max_turns=12,
    )
    assert "轮次上限停止摘要" in text
    assert "12 / 12" in text
    assert "Class2" in text
    assert "aggregate_data" in text
    assert "reports/class/Class2/overview.md" in text
    assert "建议下一步" in text


def test_break_max_turn_limit_appends_summary_message():
    loop = AgentLoop(LoopState(messages=[{"role": "user", "content": "测试问题"}]))
    loop._break_max_turn_limit(start_turn=0, turns_used=MAX_TURNS_PER_USER_ROUND)
    assert loop.loop_state.continue_reason == "max_turn_limit"
    last = loop.loop_state.messages[-1]
    assert last["role"] == "assistant"
    assert "轮次上限停止摘要" in last["content"]
