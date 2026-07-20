"""Latency / tokens / cache cost metrics (non-gating by default)."""

from __future__ import annotations

from eval.metrics.base import MetricResult
from eval.schema import Scenario
from eval.trace import RunTrace

# Rough default USD per 1M tokens (overridable later via env); for relative compare only.
# Aligned with DeepSeek V4 Flash list prices when env unset.
_DEFAULT_INPUT_PER_M = 0.14       # cache miss
_DEFAULT_OUTPUT_PER_M = 0.28
_DEFAULT_CACHED_PER_M = 0.0028    # cache hit


class CostMetric:
    name = "tokens_cost"

    def applicable(self, scenario: Scenario) -> bool:
        return True

    def evaluate(self, scenario: Scenario, trace: RunTrace) -> list[MetricResult]:
        u = trace.usage
        cached = min(int(u.cached_tokens or 0), int(u.input_tokens or 0))
        cost = (
            (u.input_tokens - cached) / 1e6 * _DEFAULT_INPUT_PER_M
            + cached / 1e6 * _DEFAULT_CACHED_PER_M
            + u.output_tokens / 1e6 * _DEFAULT_OUTPUT_PER_M
        )
        return [
            MetricResult(
                name=self.name,
                passed=True,
                score=None,
                detail=(
                    f"in={u.input_tokens} out={u.output_tokens} "
                    f"cached={u.cached_tokens} est_usd={cost:.6f}"
                ),
                tags=["cost", "efficiency"],
                evidence={
                    "input_tokens": u.input_tokens,
                    "output_tokens": u.output_tokens,
                    "cached_tokens": u.cached_tokens,
                    "llm_calls": u.llm_calls,
                    "est_usd": round(cost, 6),
                    "cache_hit_rate": u.cache_hit_rate,
                },
                hard_gate=False,
            )
        ]


class LatencyMetric:
    name = "latency"

    def applicable(self, scenario: Scenario) -> bool:
        return True

    def evaluate(self, scenario: Scenario, trace: RunTrace) -> list[MetricResult]:
        return [
            MetricResult(
                name=self.name,
                passed=True,
                score=None,
                detail=f"duration_sec={trace.duration_sec}",
                tags=["latency", "efficiency"],
                evidence={
                    "duration_sec": trace.duration_sec,
                    "turn_durations_sec": list(trace.turn_durations_sec),
                },
                hard_gate=False,
            )
        ]


class CacheHitMetric:
    name = "cache_hit_rate"

    def applicable(self, scenario: Scenario) -> bool:
        return True

    def evaluate(self, scenario: Scenario, trace: RunTrace) -> list[MetricResult]:
        rate = trace.usage.cache_hit_rate
        return [
            MetricResult(
                name=self.name,
                passed=True,
                score=rate,
                detail="n/a" if rate is None else f"cache_hit_rate={rate}",
                tags=["cache", "efficiency"],
                evidence={
                    "cache_hit_rate": rate,
                    "cached_tokens": trace.usage.cached_tokens,
                    "input_tokens": trace.usage.input_tokens,
                },
                hard_gate=False,
            )
        ]
