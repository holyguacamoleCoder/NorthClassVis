"""Loop health and step efficiency metrics."""

from __future__ import annotations

from collections import Counter

from eval.metrics.base import MetricResult
from eval.schema import Scenario
from eval.trace import RunTrace

_FAILURE_TAG_HINTS = {
    "missing_tool": ("missing aggregate", "no matching", "tool not called", "missing"),
    "llm_timeout": ("timeout", "exceeded"),
    "judge_mislabel": ("judge", "mislabel"),
    "rule_priority": ("not slice", "not broad", "rule"),
    "explicit_id_wrong": ("dataset_id mismatch", "explicit"),
}


class StepEfficiencyMetric:
    name = "step_efficiency"

    def applicable(self, scenario: Scenario) -> bool:
        return scenario.expect_max_tool_calls is not None or scenario.expect_max_turns is not None

    def evaluate(self, scenario: Scenario, trace: RunTrace) -> list[MetricResult]:
        results: list[MetricResult] = []
        n_tools = len(trace.tool_calls)
        n_turns = len(trace.user_contents) or len(scenario.turns)

        if scenario.expect_max_tool_calls is not None:
            passed = n_tools <= scenario.expect_max_tool_calls
            results.append(
                MetricResult(
                    name=self.name,
                    passed=passed,
                    score=1.0 if passed else max(0.0, scenario.expect_max_tool_calls / max(n_tools, 1)),
                    detail=(
                        "ok"
                        if passed
                        else f"tool_calls={n_tools} > max={scenario.expect_max_tool_calls}"
                    ),
                    tags=["efficiency", "loop"],
                    evidence={"tool_calls": n_tools, "max": scenario.expect_max_tool_calls},
                    hard_gate=False,
                )
            )

        if scenario.expect_max_turns is not None:
            passed = n_turns <= scenario.expect_max_turns
            results.append(
                MetricResult(
                    name=self.name,
                    passed=passed,
                    score=1.0 if passed else 0.0,
                    detail="ok" if passed else f"turns={n_turns} > max={scenario.expect_max_turns}",
                    tags=["efficiency", "loop"],
                    evidence={"turns": n_turns, "max": scenario.expect_max_turns},
                    hard_gate=False,
                )
            )
        return results


class LoopHealthMetric:
    name = "loop_health"

    def applicable(self, scenario: Scenario) -> bool:
        return True

    def evaluate(self, scenario: Scenario, trace: RunTrace) -> list[MetricResult]:
        tags: list[str] = []
        issues: list[str] = []

        if trace.status == "timeout":
            tags.append("llm_timeout")
            issues.append("run timeout")
        if trace.status in ("error", "incomplete"):
            issues.append(f"status={trace.status}")

        # Missing expected tools from expect_tools / expect_aggregates
        if scenario.expect_aggregates:
            aggs = trace.tool_calls_for("aggregate_data")
            for exp in scenario.expect_aggregates:
                turn_aggs = [e for e in aggs if e.turn_index == exp.turn_index]
                if not turn_aggs:
                    tags.append("missing_tool")
                    issues.append(f"missing aggregate turn={exp.turn_index}")

        # Oscillation: same tool signature repeated >= 4 times
        sigs = []
        for e in trace.tool_calls:
            sig = f"{e.name}:{sorted((e.tool_input or {}).keys())}"
            sigs.append(sig)
        counts = Counter(sigs)
        for sig, n in counts.items():
            if n >= 4:
                tags.append("oscillation")
                issues.append(f"repeated {sig} x{n}")
                break

        # Compact abuse
        compact_calls = [e for e in trace.tool_calls if e.name == "compact"]
        if len(compact_calls) >= 2:
            tags.append("compact_abuse")
            issues.append(f"compact called {len(compact_calls)} times")

        if trace.continue_reason and "fuse" in str(trace.continue_reason):
            tags.append("loop_fuse")
            issues.append(f"continue_reason={trace.continue_reason}")

        # Deduce failure tags from metric details already on trace
        for mr in trace.metric_results:
            detail = str(mr.get("detail") or "").lower()
            for tag, needles in _FAILURE_TAG_HINTS.items():
                if any(n in detail for n in needles):
                    tags.append(tag)

        unique_tags = sorted(set(tags))
        trace.failure_tags = sorted(set(trace.failure_tags) | set(unique_tags))
        passed = trace.status == "ok" and not any(
            t in unique_tags for t in ("llm_timeout", "missing_tool", "oscillation", "compact_abuse")
        )
        # Soft: timeout always fails health; missing expected aggregate fails
        return [
            MetricResult(
                name=self.name,
                passed=passed,
                score=1.0 if passed else 0.0,
                detail="; ".join(issues) or "healthy",
                tags=["loop"] + unique_tags,
                evidence={
                    "failure_tags": unique_tags,
                    "continue_reason": trace.continue_reason,
                    "status": trace.status,
                    "tool_calls": len(trace.tool_calls),
                },
                hard_gate=False,
            )
        ]


class FailureTagsMetric:
    name = "failure_tags"

    def applicable(self, scenario: Scenario) -> bool:
        return True

    def evaluate(self, scenario: Scenario, trace: RunTrace) -> list[MetricResult]:
        # Surface tags collected by loop_health / other metrics
        return [
            MetricResult(
                name=self.name,
                passed=True,
                score=None,
                detail=",".join(trace.failure_tags) or "none",
                tags=["diagnostics"] + list(trace.failure_tags),
                evidence={"failure_tags": list(trace.failure_tags)},
                hard_gate=False,
            )
        ]
