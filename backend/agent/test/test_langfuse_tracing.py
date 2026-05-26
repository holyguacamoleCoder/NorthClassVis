"""Langfuse tracing helpers (no cloud calls)."""

import os

import pytest

os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
os.environ.pop("LANGFUSE_SECRET_KEY", None)

from common import langfuse_tracing as lf  # noqa: E402


def test_disabled_without_keys():
    assert lf.is_enabled() is False
    with lf.user_turn_trace(
        session_id="s1",
        job_id="j1",
        user_message="hello",
    ):
        with lf.agent_turn_span(turn=0):
            with lf.llm_generation(
                name="test",
                model="gpt-4",
                messages=[{"role": "user", "content": "hi"}],
            ) as gen:
                assert gen is None
            with lf.tool_span(tool="query_data", params={"resource": "x"}) as span:
                assert span is None


def test_redact_messages():
    lf._REDACT = True
    out = lf.redact_messages([{"role": "user", "content": "secret student data"}])
    assert "secret" not in out[0]["content"]
    assert "len=" in out[0]["content"]


def test_enabled_with_keys_and_flag(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_ENABLED", "1")
    lf._client_checked = False
    lf._client = None
    assert lf.is_enabled() is True


def test_tool_error_detection():
    assert lf.is_tool_result_error("Error: missing input")
    assert not lf.is_tool_result_error('{"rows": []}')
