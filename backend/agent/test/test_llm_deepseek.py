"""DeepSeek thinking mode: reasoning_content round-trip."""

from __future__ import annotations

import os

import runtime_bootstrap  # noqa: F401, E402

from common.llm_provider import (
    deepseek_thinking_enabled,
    is_deepseek_provider,
    should_include_reasoning_content_in_api,
)
from common.message import (
    attach_reasoning_from_sdk,
    normalize_message,
    reasoning_content_from_sdk,
)


class _FakeMsg:
    def __init__(self, *, content="", reasoning_content=None, tool_calls=None):
        self.content = content
        self.reasoning_content = reasoning_content
        self.tool_calls = tool_calls


def test_reasoning_content_from_sdk():
    msg = _FakeMsg(reasoning_content="chain of thought")
    assert reasoning_content_from_sdk(msg) == "chain of thought"
    assert reasoning_content_from_sdk(_FakeMsg()) is None


def test_attach_reasoning_from_sdk():
    stored = {"role": "assistant", "content": "hi"}
    attach_reasoning_from_sdk(stored, _FakeMsg(reasoning_content="think"))
    assert stored["reasoning_content"] == "think"


def test_normalize_includes_reasoning_for_deepseek(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("DEEPSEEK_THINKING_ENABLED", "true")
    messages = [
        {
            "role": "assistant",
            "content": None,
            "reasoning_content": "internal reasoning",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "inspect_schema", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "c1", "content": "{}"},
    ]
    out = normalize_message(messages)
    assert out[0]["reasoning_content"] == "internal reasoning"


def test_normalize_omits_reasoning_for_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    messages = [
        {
            "role": "assistant",
            "content": "ok",
            "reasoning_content": "should not leak",
        }
    ]
    out = normalize_message(messages)
    assert "reasoning_content" not in out[0]


def test_normalize_force_include_reasoning():
    messages = [
        {"role": "assistant", "content": "ok", "reasoning_content": "rc"}
    ]
    out = normalize_message(messages, include_reasoning_content=True)
    assert out[0]["reasoning_content"] == "rc"


def test_provider_helpers(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.deepseek.com")
    assert is_deepseek_provider()
    assert deepseek_thinking_enabled()
    assert should_include_reasoning_content_in_api()

    monkeypatch.setenv("DEEPSEEK_THINKING_ENABLED", "false")
    assert not deepseek_thinking_enabled()
    assert not should_include_reasoning_content_in_api()

    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    assert not is_deepseek_provider(os.environ["OPENAI_BASE_URL"])
