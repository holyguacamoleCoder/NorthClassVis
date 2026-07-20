"""Guard / reject metric."""

from __future__ import annotations

from eval.metrics.base import MetricResult
from eval.schema import Scenario
from eval.trace import RunTrace

_GUARD_MARKERS = ("上一轮", "不能自动续用", "Permission denied", "permission denied", "模式限制", "不可用")


class GuardRejectMetric:
    name = "guard_reject"

    def applicable(self, scenario: Scenario) -> bool:
        if scenario.expect_error:
            return True
        return any(
            e.expect == "reject_cross_turn" or e.expect_error for e in scenario.expect_aggregates
        ) or "guard" in {t.lower() for t in scenario.tags}

    def evaluate(self, scenario: Scenario, trace: RunTrace) -> list[MetricResult]:
        results: list[MetricResult] = []

        if scenario.expect_error:
            # Mode / permission deny: expect at least one tool error or empty productive tools
            errs = [e for e in trace.tool_calls if e.is_error]
            text_blob = "\n".join(e.content for e in trace.tool_calls)
            marker_hit = any(m in text_blob for m in _GUARD_MARKERS)
            # Also accept status incomplete/timeout as soft fail for gate
            passed = bool(errs) or marker_hit or trace.status in ("ok",) and not any(
                e.name in ("query_data", "aggregate_data", "write_report") and not e.is_error
                for e in trace.tool_calls
            )
            # Stricter: if expect_error, require an error tool result or permission marker
            passed = bool(errs) or marker_hit
            results.append(
                MetricResult(
                    name=self.name,
                    passed=passed,
                    score=1.0 if passed else 0.0,
                    detail="ok" if passed else "expected guard/permission error",
                    tags=["guard"],
                    evidence={"error_tools": len(errs), "status": trace.status},
                )
            )

        for exp in scenario.expect_aggregates:
            if exp.expect != "reject_cross_turn" and not exp.expect_error:
                continue
            # Binding metric already judges; here we tag guard presence
            aggs = [
                e
                for e in trace.tool_calls_for("aggregate_data")
                if e.turn_index == exp.turn_index
            ]
            if not aggs:
                results.append(
                    MetricResult(
                        name=self.name,
                        passed=False,
                        score=0.0,
                        detail="missing aggregate for guard check",
                        tags=["guard", "missing_tool"],
                        evidence={"turn_index": exp.turn_index},
                    )
                )
                continue
            if exp.accept_guard_error:
                passed = any(e.is_error or "上一轮" in e.content for e in aggs) or any(
                    not e.is_error for e in aggs
                )
            else:
                passed = any(e.is_error or "上一轮" in e.content for e in aggs)
            results.append(
                MetricResult(
                    name=self.name,
                    passed=passed,
                    score=1.0 if passed else 0.0,
                    detail="ok" if passed else "guard reject not observed",
                    tags=["guard"],
                    evidence={"turn_index": exp.turn_index, "expect": exp.expect},
                )
            )

        if not results:
            results.append(
                MetricResult(
                    name=self.name,
                    passed=True,
                    score=1.0,
                    detail="no guard expectations",
                    tags=["guard"],
                    hard_gate=True,
                )
            )
        return results
