"""Langfuse tracing helpers (no cloud calls)."""

import os
import sys
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

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


def test_new_trace_context_ids_are_hex():
    ctx = lf._new_trace_context()
    assert len(ctx["trace_id"]) == 32
    assert len(ctx["parent_span_id"]) == 16
    int(ctx["trace_id"], 16)
    int(ctx["parent_span_id"], 16)


def test_user_turn_trace_uses_unique_trace_context_per_job(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    lf._client_checked = False
    lf._client = None
    lf._use_modern_api = True

    captured: list[dict] = []

    @contextmanager
    def fake_observation(**kwargs):
        captured.append(dict(kwargs))
        root = MagicMock()
        yield root

    @contextmanager
    def fake_propagate(**_kwargs):
        yield

    mock_client = MagicMock()
    mock_client.start_as_current_observation.side_effect = fake_observation
    mock_client.update_current_trace = MagicMock()

    fake_langfuse_mod = MagicMock()
    fake_langfuse_mod.propagate_attributes = fake_propagate

    trace_ids = iter([f"{i:032x}" for i in range(2)])

    def fake_trace_context():
        return {"trace_id": next(trace_ids), "parent_span_id": "0" * 16}

    with patch.dict(sys.modules, {"langfuse": fake_langfuse_mod}), patch.object(
        lf, "_get_client", return_value=mock_client
    ), patch.object(lf, "flush"), patch.object(lf, "_new_trace_context", side_effect=fake_trace_context):
        with lf.user_turn_trace(
            session_id="sess-a",
            job_id="job-1",
            user_message="hello",
        ):
            pass
        with lf.user_turn_trace(
            session_id="sess-a",
            job_id="job-2",
            user_message="hello again",
        ):
            pass

    assert len(captured) == 2
    assert captured[0]["trace_context"]["trace_id"] != captured[1]["trace_context"]["trace_id"]
    assert captured[0].get("trace_context") is not None
    mock_client.update_current_trace.assert_called()
