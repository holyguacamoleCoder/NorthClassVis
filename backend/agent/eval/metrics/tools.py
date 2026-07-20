"""Tool selection and argument correctness metrics."""

from __future__ import annotations

from eval.metrics.base import MetricResult, compare_value, dig_path
from eval.schema import Scenario
from eval.trace import RunTrace


class ToolCorrectnessMetric:
    name = "tool_correctness"

    def applicable(self, scenario: Scenario) -> bool:
        return bool(scenario.expect_tools) or bool(scenario.forbid_tools)

    def evaluate(self, scenario: Scenario, trace: RunTrace) -> list[MetricResult]:
        results: list[MetricResult] = []
        called = [e.name for e in trace.tool_calls]

        for exp in scenario.expect_tools:
            subset = [
                e
                for e in trace.tool_calls
                if exp.turn_index is None or e.turn_index == exp.turn_index
            ]
            names = [e.name for e in subset]
            missing = [n for n in exp.names if n not in names]
            any_ok = (not exp.any_of) or any(n in names for n in exp.any_of)
            count_ok = True
            if exp.min_count is not None:
                count_ok = len(subset) >= exp.min_count
            passed = not missing and any_ok and count_ok
            detail_parts = []
            if missing:
                detail_parts.append(f"missing={missing}")
            if not any_ok:
                detail_parts.append(f"none of any_of={exp.any_of}")
            if not count_ok:
                detail_parts.append(f"count={len(subset)} < min={exp.min_count}")
            results.append(
                MetricResult(
                    name=self.name,
                    passed=passed,
                    score=1.0 if passed else 0.0,
                    detail="; ".join(detail_parts) or "ok",
                    tags=["tools"],
                    evidence={"turn_index": exp.turn_index, "called": names},
                )
            )

        for forbidden in scenario.forbid_tools:
            hit = [e for e in trace.tool_calls if e.name == forbidden]
            passed = not hit
            results.append(
                MetricResult(
                    name="forbid_tools",
                    passed=passed,
                    score=1.0 if passed else 0.0,
                    detail="ok" if passed else f"forbidden tool called: {forbidden}",
                    tags=["tools", "forbid"],
                    evidence={"tool": forbidden, "count": len(hit)},
                )
            )

        if not results and scenario.forbid_tools is None and not scenario.expect_tools:
            results.append(
                MetricResult(
                    name=self.name,
                    passed=True,
                    score=1.0,
                    detail="no tool expectations",
                    tags=["tools"],
                    evidence={"called": called},
                )
            )
        return results


class ArgCorrectnessMetric:
    name = "arg_correctness"

    def applicable(self, scenario: Scenario) -> bool:
        return bool(scenario.expect_args)

    def evaluate(self, scenario: Scenario, trace: RunTrace) -> list[MetricResult]:
        results: list[MetricResult] = []
        for exp in scenario.expect_args:
            candidates = [
                e
                for e in trace.tool_calls
                if e.name == exp.tool
                and (exp.turn_index is None or e.turn_index == exp.turn_index)
                and (exp.ordinal is None or e.ordinal == exp.ordinal)
            ]
            if not candidates:
                results.append(
                    MetricResult(
                        name=self.name,
                        passed=False,
                        score=0.0,
                        detail=f"no {exp.tool} call for args check",
                        tags=["tools", "args"],
                        evidence={"tool": exp.tool, "path": exp.path},
                    )
                )
                continue
            # Prefer last matching call (after retries)
            ev = candidates[-1]
            actual = dig_path(ev.tool_input, exp.path)
            ok, reason = compare_value(
                actual,
                eq=exp.eq,
                gte=exp.gte,
                lte=exp.lte,
                contains=exp.contains,
                exists=exp.exists,
            )
            results.append(
                MetricResult(
                    name=self.name,
                    passed=ok,
                    score=1.0 if ok else 0.0,
                    detail=reason,
                    tags=["tools", "args"],
                    evidence={
                        "tool": exp.tool,
                        "path": exp.path,
                        "actual": actual,
                        "turn_index": ev.turn_index,
                        "ordinal": ev.ordinal,
                    },
                )
            )
        return results
