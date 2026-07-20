"""Scope / UI attachment contract metric."""

from __future__ import annotations

from eval.metrics.base import MetricResult
from eval.schema import Scenario
from eval.trace import RunTrace


class ScopeContractMetric:
    name = "scope_contract"

    def applicable(self, scenario: Scenario) -> bool:
        return scenario.expect_scope is not None or scenario.ui_scope is not None

    def evaluate(self, scenario: Scenario, trace: RunTrace) -> list[MetricResult]:
        expect = scenario.expect_scope
        user_blob = "\n".join(trace.user_contents)
        hard = bool(expect.hard) if expect else False

        must_contain = list(expect.must_contain) if expect else []
        # Soft defaults when expect_scope absent: visible scope facts, not UI chrome.
        if expect is None and scenario.ui_scope:
            ui = scenario.ui_scope
            if ui.get("classes"):
                must_contain.append(str(ui["classes"][0]))
            if ui.get("selected_student_ids"):
                # Preview IDs appear in the turn-scope hint; do not require chrome markers.
                preview = [str(x) for x in ui["selected_student_ids"][:1] if x]
                must_contain.extend(preview)
            if ui.get("knowledge_ids"):
                must_contain.append("知识点")
                must_contain.append(str(ui["knowledge_ids"][0]))
            if isinstance(ui.get("view_snapshot"), dict):
                must_contain.append("视图快照")
            if isinstance(ui.get("report"), dict):
                must_contain.append("继续编辑报告")
            if isinstance(ui.get("dataset"), dict):
                must_contain.append("基于查询结果")

        # Drop product-chrome needles that may be stripped from display / merged turns.
        must_contain = [
            n
            for n in must_contain
            if n and n not in ("[系统·本轮范围]", "系统·本轮范围")
        ]

        missing: list[str] = []
        for needle in must_contain:
            if needle not in user_blob:
                missing.append(f"missing:{needle}")

        must_call = list(expect.must_call_tools) if expect else []
        called = {e.name for e in trace.tool_calls}
        for tool in must_call:
            if tool not in called:
                missing.append(f"tool:{tool}")

        passed = not missing
        if not must_contain and not must_call:
            detail = "no scope assertions"
            passed = True
        elif passed:
            detail = "ok"
        else:
            detail = "; ".join(missing)

        return [
            MetricResult(
                name=self.name,
                passed=passed,
                score=1.0 if passed else 0.0,
                detail=detail,
                tags=["scope"],
                evidence={
                    "must_contain": must_contain,
                    "must_call_tools": must_call,
                    "missing": missing,
                },
                hard_gate=hard,
            )
        ]
