"""HTTP adapter: extract pre-tool thinking from turn messages."""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agent.http.adapter import adapt_legacy_query_response  # noqa: E402


def test_thinking_from_assistant_before_tools():
    messages = [
        {"role": "user", "content": "有哪些 majors？"},
        {
            "role": "assistant",
            "content": "先查 student_info 的专业字段分布。",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "inspect_schema", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "c1", "content": "{}"},
        {
            "role": "assistant",
            "content": "共有 5 个专业代码。",
        },
    ]
    res = adapt_legacy_query_response(messages)
    assert res["thinking"] == "先查 student_info 的专业字段分布。"
    assert res["answer"] == "共有 5 个专业代码。"


def test_no_thinking_when_only_final_answer():
    messages = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！"},
    ]
    res = adapt_legacy_query_response(messages)
    assert res["thinking"] == ""
    assert res["answer"] == "你好！"
