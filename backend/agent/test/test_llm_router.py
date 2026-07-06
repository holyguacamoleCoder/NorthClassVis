"""Tests for per-call-site LLM routing."""

from __future__ import annotations

import os
from unittest.mock import patch

from common.llm_client import LLMClient, LLMConfig
from common.llm_router import LLMRouter
from permission.modes import CapabilityMode


def _client(model: str) -> LLMClient:
    return LLMClient(LLMConfig(api_key="k", base_url="https://api.example/v1", model=model))


def test_from_single_client_uses_same_model_everywhere():
    router = LLMRouter.from_single_client(_client("same-model"))
    summary = router.models_summary()
    assert summary == {k: "same-model" for k in summary}


def test_main_for_mode_routes_by_capability():
    router = LLMRouter(
        main=_client("main"),
        consult=_client("consult"),
        produce=_client("produce"),
        binding=_client("binding"),
        compact=_client("compact"),
    )
    assert router.main_for_mode(CapabilityMode.ANALYZE).config.model == "main"
    assert router.main_for_mode(CapabilityMode.CONSULT).config.model == "consult"
    assert router.main_for_mode(CapabilityMode.PRODUCE).config.model == "produce"
    assert router.main_for_mode("analyze").config.model == "main"


@patch.dict(
    os.environ,
    {
        "OPENAI_API_KEY": "k",
        "OPENAI_BASE_URL": "https://api.example/v1",
        "OPENAI_MODEL": "base",
        "OPENAI_MODEL_MAIN": "main-model",
        "OPENAI_MODEL_CONSULT": "consult-model",
        "OPENAI_MODEL_PRODUCE": "produce-model",
        "OPENAI_MODEL_BINDING": "binding-model",
        "OPENAI_MODEL_COMPACT": "compact-model",
    },
    clear=False,
)
def test_from_env_resolves_per_role_models():
    router = LLMRouter.from_env()
    assert router.models_summary() == {
        "main": "main-model",
        "consult": "consult-model",
        "produce": "produce-model",
        "binding": "binding-model",
        "compact": "compact-model",
    }


@patch.dict(
    os.environ,
    {
        "OPENAI_API_KEY": "k",
        "OPENAI_MODEL": "only-one",
    },
    clear=False,
)
def test_from_env_falls_back_to_openai_model():
    router = LLMRouter.from_env()
    assert router.models_summary() == {k: "only-one" for k in router.models_summary()}


def test_create_completion_model_override():
    client = _client("default")
    captured: dict[str, str] = {}

    class _FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return None

    class _FakeClient:
        chat = type("Chat", (), {"completions": _FakeCompletions()})()

    client.set_client(_FakeClient())
    client.create_completion(
        system_prompt="sys",
        messages=[{"role": "user", "content": "hi"}],
        model="override-model",
    )
    assert captured.get("model") == "override-model"
