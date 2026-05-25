"""Tests for HTTP response adapter."""

from __future__ import annotations

import json
import os
import sys

import pytest

_AGENT_ROOT = os.path.join(os.path.dirname(__file__), "..")
if _AGENT_ROOT not in sys.path:
    sys.path.insert(0, _AGENT_ROOT)

from http_adapter import (  # noqa: E402
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
