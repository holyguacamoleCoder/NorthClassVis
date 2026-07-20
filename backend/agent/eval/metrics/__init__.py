"""Metric registry for the agent benchmark harness."""

from __future__ import annotations

from eval.metrics.binding import BindingMetric
from eval.metrics.cost import CacheHitMetric, CostMetric, LatencyMetric
from eval.metrics.guard import GuardRejectMetric
from eval.metrics.loop import FailureTagsMetric, LoopHealthMetric, StepEfficiencyMetric
from eval.metrics.scope import ScopeContractMetric
from eval.metrics.task import TaskSuccessMetric
from eval.metrics.tools import ArgCorrectnessMetric, ToolCorrectnessMetric
from eval.schema import Scenario
from eval.trace import RunTrace


def default_metrics() -> list:
    return [
        BindingMetric(),
        ToolCorrectnessMetric(),
        ArgCorrectnessMetric(),
        ScopeContractMetric(),
        GuardRejectMetric(),
        TaskSuccessMetric(),
        StepEfficiencyMetric(),
        LoopHealthMetric(),
        FailureTagsMetric(),
        LatencyMetric(),
        CostMetric(),
        CacheHitMetric(),
    ]


def evaluate_all(scenario: Scenario, trace: RunTrace, metrics: list | None = None) -> list:
    """Run applicable metrics. Loop health runs after others so it can see prior results."""
    registry = metrics or default_metrics()
    early = [m for m in registry if m.name not in ("loop_health", "failure_tags")]
    late = [m for m in registry if m.name in ("loop_health", "failure_tags")]

    results = []
    for m in early:
        if not m.applicable(scenario):
            continue
        batch = m.evaluate(scenario, trace)
        results.extend(batch)
        trace.metric_results.extend([r.to_dict() for r in batch])

    for m in late:
        if not m.applicable(scenario):
            continue
        batch = m.evaluate(scenario, trace)
        results.extend(batch)
        trace.metric_results.extend([r.to_dict() for r in batch])

    return results
