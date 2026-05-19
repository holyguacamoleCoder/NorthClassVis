import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from common.llm_client import LLMCallError
from recovery.backoff import backoff_delay
from recovery.classify import RecoveryAction, classify_exception, is_output_truncated
from recovery.config import RecoveryConfig
from recovery.handler import RecoveryHandler


def test_is_output_truncated():
    assert is_output_truncated("length")
    assert is_output_truncated("max_tokens")
    assert not is_output_truncated("stop")
    assert not is_output_truncated("tool_calls")


def test_classify_context_overflow():
    exc = Exception("Error: maximum context length exceeded")
    assert classify_exception(exc) == RecoveryAction.COMPACT


def test_classify_transient():
    assert classify_exception(TimeoutError("timed out")) == RecoveryAction.BACKOFF
    exc = Exception("rate limit exceeded")
    assert classify_exception(exc) == RecoveryAction.BACKOFF


def test_backoff_delay_grows_with_attempt():
    config = RecoveryConfig(backoff_base_delay=1.0, backoff_max_delay=30.0)
    assert backoff_delay(0, config=config) >= 1.0
    assert backoff_delay(2, config=config) >= backoff_delay(0, config=config)


def _make_response(*, finish_reason: str = "stop", content: str = "ok", tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice])


def test_recovery_continues_on_length():
    config = RecoveryConfig(enabled=True, max_attempts=3)
    client = MagicMock()
    client.create_completion.side_effect = [
        _make_response(finish_reason="length", content="part one"),
        _make_response(finish_reason="stop", content="part two"),
    ]
    messages = [{"role": "user", "content": "hi"}]
    handler = RecoveryHandler(client, config=config)

    response, reason = handler.request_completion(
        system_prompt="sys",
        messages=messages,
        tools=[],
        max_tokens=100,
        normalize_fn=lambda m: m,
        compact_fn=lambda: None,
    )

    assert reason is None
    assert response is not None
    assert client.create_completion.call_count == 2
    assert messages[-2]["role"] == "assistant"
    assert messages[-1]["role"] == "user"
    assert "长度上限" in messages[-1]["content"]


def test_recovery_compacts_on_context_error():
    config = RecoveryConfig(enabled=True, max_attempts=2)
    client = MagicMock()
    client.create_completion.side_effect = [
        LLMCallError("maximum context length exceeded"),
        _make_response(finish_reason="stop"),
    ]
    compacted = {"called": False}

    def compact_fn():
        compacted["called"] = True

    handler = RecoveryHandler(client, config=config)
    response, reason = handler.request_completion(
        system_prompt="sys",
        messages=[{"role": "user", "content": "hi"}],
        tools=[],
        max_tokens=100,
        normalize_fn=lambda m: m,
        compact_fn=compact_fn,
    )

    assert reason is None
    assert response is not None
    assert compacted["called"]
    assert client.create_completion.call_count == 2


def test_recovery_backoff_on_transient(monkeypatch):
    config = RecoveryConfig(enabled=True, max_attempts=2, backoff_base_delay=0.01)
    client = MagicMock()
    client.create_completion.side_effect = [
        LLMCallError("connection timed out", cause=TimeoutError("connection timed out")),
        _make_response(finish_reason="stop"),
    ]
    sleeps: list[float] = []
    monkeypatch.setattr("recovery.handler.sleep_backoff", lambda attempt, **kw: sleeps.append(attempt) or 0.0)

    handler = RecoveryHandler(client, config=config)
    response, reason = handler.request_completion(
        system_prompt="sys",
        messages=[{"role": "user", "content": "hi"}],
        tools=[],
        max_tokens=100,
        normalize_fn=lambda m: m,
        compact_fn=lambda: None,
    )

    assert reason is None
    assert response is not None
    assert sleeps == [0]
