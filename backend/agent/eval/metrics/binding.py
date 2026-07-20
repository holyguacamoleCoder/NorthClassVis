"""Binding accuracy metric — wraps existing binding_judge."""

from __future__ import annotations

from eval.binding_judge import judge_aggregate
from eval.metrics.base import MetricResult
from eval.schema import ExpectAggregate, Scenario
from eval.trace import RunTrace, ToolCallEvent


class BindingMetric:
    name = "binding_accuracy"

    def applicable(self, scenario: Scenario) -> bool:
        return bool(scenario.expect_aggregates)

    def evaluate(self, scenario: Scenario, trace: RunTrace) -> list[MetricResult]:
        events = trace.tool_calls_for("aggregate_data")
        used: set[int] = set()
        results: list[MetricResult] = []

        for exp in scenario.expect_aggregates:
            matched = self._match_event(exp, events, used, scenario, trace)
            if matched is None:
                results.append(
                    MetricResult(
                        name=self.name,
                        passed=False,
                        score=0.0,
                        detail="missing aggregate",
                        tags=["binding", "missing_tool"],
                        evidence={
                            "turn_index": exp.turn_index,
                            "ordinal": exp.ordinal,
                            "expect": exp.expect,
                        },
                    )
                )
                continue

            idx, ev = matched
            used.add(idx)
            meta = dict(ev.meta or {})
            meta["session_id"] = trace.session_id
            ok, reason = judge_aggregate(
                exp.expect,
                meta=meta,
                catalog=trace.catalog,
                content=ev.content,
                tool_input=ev.tool_input,
                current_user_turn=exp.turn_index + 1,
                accept_guard_error=exp.accept_guard_error,
            )
            if exp.expect_error and not ev.is_error:
                ok = False
                reason = "expected guard error but aggregate succeeded"
            results.append(
                MetricResult(
                    name=self.name,
                    passed=ok,
                    score=1.0 if ok else 0.0,
                    detail=reason,
                    tags=["binding"],
                    evidence={
                        "turn_index": exp.turn_index,
                        "ordinal": exp.ordinal or ev.ordinal,
                        "expect": exp.expect,
                        "resolver": ev.resolver,
                        "result_ref": meta.get("result_ref"),
                        "dataset_id": meta.get("dataset_id"),
                        "is_error": ev.is_error,
                    },
                )
            )
        return results

    def _match_event(
        self,
        exp: ExpectAggregate,
        events: list[ToolCallEvent],
        used: set[int],
        scenario: Scenario,
        trace: RunTrace,
    ) -> tuple[int, ToolCallEvent] | None:
        turn_events = [
            (i, ev)
            for i, ev in enumerate(events)
            if i not in used and ev.turn_index == exp.turn_index
        ]
        if not turn_events:
            return None
        if exp.ordinal is not None:
            for i, ev in turn_events:
                if ev.ordinal == exp.ordinal:
                    return i, ev
            return None

        if exp.accept_guard_error:
            for i, ev in turn_events:
                meta_try = dict(ev.meta or {})
                meta_try["session_id"] = trace.session_id
                ok, _ = judge_aggregate(
                    exp.expect,
                    meta=meta_try,
                    catalog=trace.catalog,
                    content=ev.content,
                    tool_input=ev.tool_input,
                    current_user_turn=exp.turn_index + 1,
                    accept_guard_error=True,
                )
                if ok:
                    return i, ev
            return turn_events[-1]

        return turn_events[-1]
