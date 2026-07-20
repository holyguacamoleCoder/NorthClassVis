"""Task success metric — declarative final assertions."""

from __future__ import annotations

import json
import re

from eval.metrics.base import MetricResult, compare_value, dig_path
from eval.schema import Scenario
from eval.trace import RunTrace


class TaskSuccessMetric:
    name = "task_success"

    def applicable(self, scenario: Scenario) -> bool:
        return scenario.expect_task is not None

    def evaluate(self, scenario: Scenario, trace: RunTrace) -> list[MetricResult]:
        assert scenario.expect_task is not None
        results: list[MetricResult] = []
        for assertion in scenario.expect_task.asserts:
            ok, detail, evidence = self._eval_one(assertion.kind, assertion, trace)
            results.append(
                MetricResult(
                    name=self.name,
                    passed=ok,
                    score=1.0 if ok else 0.0,
                    detail=detail,
                    tags=["task"],
                    evidence=evidence,
                )
            )
        if not results:
            results.append(
                MetricResult(
                    name=self.name,
                    passed=True,
                    score=1.0,
                    detail="empty expect_task",
                    tags=["task"],
                )
            )
        return results

    def _eval_one(self, kind: str, a, trace: RunTrace) -> tuple[bool, str, dict]:
        tools = [
            e
            for e in trace.tool_calls
            if (a.tool is None or e.name == a.tool)
            and (a.turn_index is None or e.turn_index == a.turn_index)
        ]
        evidence: dict = {"kind": kind, "tool": a.tool}

        if kind == "tool_succeeded":
            ok_tools = [e for e in tools if not e.is_error]
            if not ok_tools:
                return False, f"no successful {a.tool or 'tool'}", evidence
            return True, "ok", {**evidence, "count": len(ok_tools)}

        if kind == "tool_called":
            if not tools:
                return False, f"tool not called: {a.tool}", evidence
            return True, "ok", {**evidence, "count": len(tools)}

        if kind == "aggregate_has_metric":
            aggs = [e for e in tools if e.name == "aggregate_data"] or trace.tool_calls_for(
                "aggregate_data"
            )
            if a.turn_index is not None:
                aggs = [e for e in aggs if e.turn_index == a.turn_index]
            for ev in aggs:
                metrics = dig_path(ev.tool_input, "metrics") or []
                for m in metrics:
                    if not isinstance(m, dict):
                        continue
                    if a.metric_op and str(m.get("op")) != a.metric_op:
                        continue
                    if a.field and str(m.get("field") or "") != a.field:
                        continue
                    return True, "ok", {**evidence, "metric": m}
            return False, f"metric op={a.metric_op} field={a.field} not found", evidence

        if kind == "numeric_in_tool_result":
            if not tools:
                return False, "no tool result", evidence
            ev = tools[-1]
            value = None
            try:
                payload = json.loads(ev.content)
            except json.JSONDecodeError:
                payload = None
            if a.path and payload is not None:
                value = dig_path(payload, a.path)
            elif payload is not None:
                rows = payload.get("rows") if isinstance(payload, dict) else None
                if isinstance(rows, list) and rows:
                    first = rows[0]
                    if isinstance(first, (list, tuple)) and first:
                        value = first[0]
                    elif isinstance(first, (int, float)):
                        value = first
            ok, reason = compare_value(value, eq=a.value if a.op in (None, "eq") else None)
            if a.op == "gt":
                ok, reason = compare_value(value, gte=(float(a.value) + 1e-9) if a.value is not None else None)
                # use raw compare
                try:
                    ok = value is not None and float(value) > float(a.value)
                    reason = "ok" if ok else f"{value} not > {a.value}"
                except (TypeError, ValueError):
                    ok, reason = False, f"cannot compare {value}"
            elif a.op == "gte":
                ok, reason = compare_value(value, gte=a.value)
            elif a.op == "lte":
                ok, reason = compare_value(value, lte=a.value)
            elif a.op == "approx" and a.value is not None:
                try:
                    ok = value is not None and abs(float(value) - float(a.value)) <= max(
                        0.05 * abs(float(a.value)), 0.5
                    )
                    reason = "ok" if ok else f"{value} not approx {a.value}"
                except (TypeError, ValueError):
                    ok, reason = False, f"cannot approx-compare {value}"
            return ok, reason, {**evidence, "value": value}

        if kind == "content_regex":
            blob = "\n".join(e.content for e in (tools or trace.tool_calls))
            pattern = str(a.value or "")
            if not pattern:
                return False, "missing regex", evidence
            ok = bool(re.search(pattern, blob))
            return ok, "ok" if ok else f"regex not matched: {pattern}", evidence

        if kind == "status_ok":
            ok = trace.status == "ok"
            return ok, "ok" if ok else f"status={trace.status}", evidence

        return False, f"unknown assert kind: {kind}", evidence
