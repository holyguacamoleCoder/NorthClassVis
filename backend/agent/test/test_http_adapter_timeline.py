"""HTTP adapter: interleaved turn timeline."""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agent.http.adapter import adapt_legacy_query_response, build_turn_timeline  # noqa: E402


def test_timeline_interleaves_narration_and_tools():
    messages = [
        {"role": "user", "content": "分析 Class1"},
        {
            "role": "assistant",
            "content": "先查 week_aggregation。",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "query_data", "arguments": '{"resource":"week_aggregation"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "c1", "content": '{"rows": [], "meta": {}}'},
        {
            "role": "assistant",
            "content": "继续聚合弱项。",
            "tool_calls": [
                {
                    "id": "c2",
                    "type": "function",
                    "function": {"name": "aggregate_data", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "c2", "content": "Error: missing input"},
        {"role": "assistant", "content": "Class1 班均 0.81。"},
    ]
    timeline = build_turn_timeline(messages[1:])
    kinds = [item["kind"] for item in timeline]
    assert kinds == ["narration", "tool", "narration", "tool", "narration"]
    assert timeline[0]["phase"] == "plan"
    assert timeline[2]["phase"] == "plan_update"
    assert timeline[4]["phase"] == "conclusion"

    res = adapt_legacy_query_response(messages)
    assert len(res["timeline"]) == 5
    assert res["thinking"] == "先查 week_aggregation。"
    assert res["thinking_updates"] == ["继续聚合弱项。"]
    assert res["closing"] == "Class1 班均 0.81。"


def test_timeline_simple_chat():
    messages = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "你好"},
    ]
    res = adapt_legacy_query_response(messages)
    assert len(res["timeline"]) == 1
    assert res["timeline"][0]["phase"] == "conclusion"
    assert res["answer"] == "你好"
