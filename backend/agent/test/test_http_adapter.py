"""Tests for HTTP response adapter."""

from __future__ import annotations

import json
import os
import sys

import pytest

_BACKEND_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from agent.http.adapter import (  # noqa: E402
    adapt_legacy_query_response,
    extract_tool_steps,
    serialize_messages,
)


def test_extract_tool_steps_ok_and_fail():
    messages = [
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {
                        "name": "query_data",
                        "arguments": json.dumps({"resource": "student_info"}),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "c1",
            "content": json.dumps({"rows": [{"a": 1}], "meta": {"truncated": False}}),
        },
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "c2",
                    "type": "function",
                    "function": {"name": "write_file", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "c2", "content": "Permission denied for write_file"},
    ]
    steps = extract_tool_steps(messages)
    assert len(steps) == 2
    assert steps[0]["status"] == "ok"
    assert steps[0]["tool"] == "query_data"
    assert steps[1]["status"] == "denied"


def test_adapt_legacy_includes_visual_links():
    link_payload = {"visual_links": [{"view": "WeekView", "params": {"kind": 1}}]}
    messages = [
        {"role": "user", "content": "趋势"},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "build_visual_links", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "c1", "content": json.dumps(link_payload)},
        {"role": "assistant", "content": "请看图表。"},
    ]
    out = adapt_legacy_query_response(messages)
    assert out["answer"] == "请看图表。"
    assert len(out["visual_links"]) == 1
    assert out["visual_links"][0]["view"] == "WeekView"


def test_serialize_messages_shape():
    messages = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    serialized = serialize_messages(messages)
    assert serialized[0]["role"] == "user"
    assert serialized[1]["content"] == "hello"


def test_serialize_messages_hides_compact_summary():
    from agent.common.prompts import COMPACT_USER_MESSAGE_PREAMBLE

    messages = [
        {
            "role": "user",
            "content": f"{COMPACT_USER_MESSAGE_PREAMBLE}\n\n内部摘要",
            "_agent_meta": {"ui_visible": False, "content_kind": "compact_summary"},
        },
        {"role": "user", "content": "继续分析"},
        {"role": "assistant", "content": "好的"},
    ]
    serialized = serialize_messages(messages)
    assert len(serialized) == 2
    assert serialized[0]["content"] == "继续分析"
    assert serialized[1]["content"] == "好的"


def test_serialize_messages_hides_legacy_compact_without_meta():
    from agent.common.prompts import COMPACT_USER_MESSAGE_PREAMBLE

    messages = [
        {"role": "user", "content": f"{COMPACT_USER_MESSAGE_PREAMBLE}\n\nlegacy"},
        {"role": "assistant", "content": "ok"},
    ]
    serialized = serialize_messages(messages)
    assert len(serialized) == 1
    assert serialized[0]["role"] == "assistant"


def test_serialize_messages_strips_ui_scope_injection():
    messages = [
        {
            "role": "user",
            "content": (
                "只分析选中学生\n\n"
                "[系统·UI 同步] 教师已在可视化面板选中学生，请直接用于 query_data / 分析：\n"
                "student_ID: a, b（共 2 人）"
            ),
        },
        {"role": "assistant", "content": "好"},
    ]
    serialized = serialize_messages(messages)
    assert serialized[0]["content"] == "只分析选中学生"
    assert "UI 同步" not in serialized[0]["content"]
    assert "student_ID" not in serialized[0]["content"]


def test_serialize_messages_includes_ui_scope():
    messages = [
        {
            "role": "user",
            "content": "只分析选中学生",
            "ui_scope": {"selected_student_ids": ["abc"]},
        },
        {"role": "assistant", "content": "好"},
    ]
    serialized = serialize_messages(messages)
    assert serialized[0]["ui_scope"]["selected_student_ids"] == ["abc"]

