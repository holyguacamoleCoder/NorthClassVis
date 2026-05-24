import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from common.message import coerce_tool_calls_for_api, normalize_message


def test_coerce_sdk_tool_call_object():
    sdk_tc = SimpleNamespace(
        id="call_abc",
        type="function",
        function=SimpleNamespace(name="query_data", arguments='{"resource": "student_info"}'),
    )
    out = coerce_tool_calls_for_api([sdk_tc])
    assert len(out) == 1
    assert out[0]["id"] == "call_abc"
    assert out[0]["function"]["name"] == "query_data"
    assert isinstance(out[0]["function"]["arguments"], str)


def test_normalize_message_rejects_string_tool_calls_element():
    payload = [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "inspect_schema", "arguments": "{}"},
        }
    ]
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [json.dumps(payload[0])],  # bad: element is str
        }
    ]
    out = normalize_message(messages)
    assert isinstance(out[0]["tool_calls"][0], dict)
    assert out[0]["tool_calls"][0]["function"]["name"] == "inspect_schema"


def test_normalize_drops_orphan_tool_messages():
    messages = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": ""},
        {"role": "tool", "tool_call_id": "orphan", "content": "stale result"},
    ]
    out = normalize_message(messages)
    assert [m.get("role") for m in out] == ["user", "assistant"]


def test_normalize_keeps_valid_tool_chain():
    calls = [
        {
            "id": "call_ok",
            "type": "function",
            "function": {"name": "inspect_schema", "arguments": "{}"},
        }
    ]
    messages = [
        {"role": "assistant", "content": "", "tool_calls": calls},
        {"role": "tool", "tool_call_id": "call_ok", "content": "ok"},
        {"role": "user", "content": "continue"},
    ]
    out = normalize_message(messages)
    assert [m.get("role") for m in out] == ["assistant", "tool", "user"]
    assert out[0]["tool_calls"][0]["id"] == "call_ok"


def test_normalize_drops_tools_when_tool_calls_coercion_fails():
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": ["ChatCompletionMessageToolCall(invalid repr)"],
        },
        {"role": "tool", "tool_call_id": "call_x", "content": "orphan"},
    ]
    out = normalize_message(messages)
    roles = [m.get("role") for m in out]
    assert "tool" not in roles
    assert "tool_calls" not in (out[0] if out else {})


def test_normalize_message_parses_json_string_tool_calls():
    calls = [
        {
            "id": "call_2",
            "type": "function",
            "function": {"name": "read_file", "arguments": '{"path": "x"}'},
        }
    ]
    messages = [{"role": "assistant", "content": "", "tool_calls": json.dumps(calls)}]
    out = normalize_message(messages)
    assert out[0]["tool_calls"][0]["function"]["name"] == "read_file"


def test_normalize_appends_placeholder_for_missing_tool_results():
    calls = [
        {
            "id": "call_a",
            "type": "function",
            "function": {"name": "query_data", "arguments": "{}"},
        },
        {
            "id": "call_b",
            "type": "function",
            "function": {"name": "query_data", "arguments": "{}"},
        },
    ]
    messages = [
        {"role": "assistant", "content": "", "tool_calls": calls},
        {"role": "tool", "tool_call_id": "call_a", "content": "ok"},
    ]
    out = normalize_message(messages)
    assert [m.get("role") for m in out] == ["assistant", "tool", "tool"]
    assert out[1]["tool_call_id"] == "call_a"
    assert out[2]["tool_call_id"] == "call_b"
    assert "missing" in out[2]["content"].lower() or "deduplicated" in out[2]["content"].lower()
