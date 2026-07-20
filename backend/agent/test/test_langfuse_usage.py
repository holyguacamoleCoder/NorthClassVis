"""Unit tests for Langfuse usage / cache field extraction."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from common.langfuse_tracing import _usage_details  # noqa: E402


def test_usage_details_basic():
    resp = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=40)
    )
    assert _usage_details(resp) == {"input": 1000, "output": 40}


def test_usage_details_includes_openai_cached_tokens():
    resp = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=8000,
            completion_tokens=100,
            prompt_tokens_details=SimpleNamespace(cached_tokens=6500),
        )
    )
    details = _usage_details(resp)
    assert details["input"] == 8000
    assert details["input_cached_tokens"] == 6500
    assert details["cache_read_input_tokens"] == 6500


def test_usage_details_includes_deepseek_style_cache_hit():
    resp = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=5000,
            completion_tokens=20,
            prompt_cache_hit_tokens=4200,
        )
    )
    details = _usage_details(resp)
    assert details["input_cached_tokens"] == 4200
