"""Route LLM calls to different models by call site (single-agent multi-model)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from common.llm_client import LLMClient, LLMConfig

if TYPE_CHECKING:
    from permission.modes import CapabilityMode


def _env_model(name: str) -> str | None:
    value = (os.environ.get(name) or "").strip()
    return value or None


def _resolve_model(*keys: str, fallback: str) -> str:
    for key in keys:
        value = _env_model(key)
        if value:
            return value
    return fallback


@dataclass(frozen=True)
class LLMRouter:
    """Per-call-site LLM clients for a single AgentLoop."""

    main: LLMClient
    consult: LLMClient
    produce: LLMClient
    binding: LLMClient
    compact: LLMClient

    @classmethod
    def from_env(cls) -> LLMRouter:
        base = LLMConfig.from_env()
        default = base.model
        main_model = _resolve_model("OPENAI_MODEL_MAIN", "OPENAI_MODEL", fallback=default)
        consult_model = _resolve_model("OPENAI_MODEL_CONSULT", fallback=main_model)
        produce_model = _resolve_model("OPENAI_MODEL_PRODUCE", fallback=main_model)
        binding_model = _resolve_model("OPENAI_MODEL_BINDING", fallback=main_model)
        compact_model = _resolve_model("OPENAI_MODEL_COMPACT", fallback=binding_model)

        def _client(model: str) -> LLMClient:
            return LLMClient(
                LLMConfig(api_key=base.api_key, base_url=base.base_url, model=model)
            )

        return cls(
            main=_client(main_model),
            consult=_client(consult_model),
            produce=_client(produce_model),
            binding=_client(binding_model),
            compact=_client(compact_model),
        )

    @classmethod
    def from_single_client(cls, client: LLMClient) -> LLMRouter:
        """Backward-compatible wrapper when only one client is configured."""
        return cls(
            main=client,
            consult=client,
            produce=client,
            binding=client,
            compact=client,
        )

    def main_for_mode(self, mode: CapabilityMode | str) -> LLMClient:
        from permission.modes import CapabilityMode

        key = mode.value if isinstance(mode, CapabilityMode) else str(mode).strip().lower()
        if key == CapabilityMode.CONSULT.value:
            return self.consult
        if key == CapabilityMode.PRODUCE.value:
            return self.produce
        return self.main

    def models_summary(self) -> dict[str, str]:
        return {
            "main": self.main.config.model,
            "consult": self.consult.config.model,
            "produce": self.produce.config.model,
            "binding": self.binding.config.model,
            "compact": self.compact.config.model,
        }


_default_router: LLMRouter | None = None


def get_default_llm_router() -> LLMRouter:
    global _default_router
    if _default_router is None:
        _default_router = LLMRouter.from_env()
    return _default_router
