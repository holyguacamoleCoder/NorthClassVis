# 厚工具：按主体「班级」聚合，mode 控制内部行为。

import time
from typing import Any, Dict, List

from agent.tools.base import BaseTool
from agent.tools.base import make_tool_result
from agent.tools.base import param_schema
from agent.tools.trend import run_get_week_data
from agent.tools.trend import run_get_peak_data
from agent.tools.cluster import run_get_cluster_everyone
from agent.tools.cluster import run_get_scatter


VALID_MODES = ("trend", "cluster")


def _merge_steps(
    summary1: str,
    step1: Dict[str, Any],
    summary2: str,
    step2: Dict[str, Any],
    tool_name: str,
    params: Dict[str, Any],
) -> tuple:
    """合并两次调用的 summary、evidence、visual_hints、coverage，返回 (merged_summary, merged_step)。"""
    merged_summary = f"{summary1}；{summary2}"
    evidence1 = list(step1.get("evidence") or [])
    if not evidence1 and summary1:
        evidence1 = [{"tool": step1.get("tool", ""), "summary": summary1}]
    evidence2 = list(step2.get("evidence") or [])
    if not evidence2 and summary2:
        evidence2 = [{"tool": step2.get("tool", ""), "summary": summary2}]
    merged_evidence = evidence1 + evidence2
    for e in merged_evidence:
        if isinstance(e, dict):
            e["tool"] = e.get("tool") or tool_name
    visual_hints = list(step1.get("visual_hints") or []) + list(step2.get("visual_hints") or [])
    raw = {"first": step1.get("raw"), "second": step2.get("raw")}
    cov1 = step1.get("coverage") or {}
    cov2 = step2.get("coverage") or {}
    merged_covered = cov1.get("covered") is True and cov2.get("covered") is True
    reason = cov1.get("reason") or cov2.get("reason") or "样本不足"
    step = {
        "tool": tool_name,
        "params": params,
        "summary": merged_summary,
        "evidence": merged_evidence,
        "visual_hints": visual_hints,
        "raw": raw,
        "coverage": {"covered": merged_covered, "reason": reason} if not merged_covered else {"covered": True},
    }
    return merged_summary, step


class QueryClassTool(BaseTool):
    """query_class：班级维度厚工具，mode=trend|cluster 各合并两次 run_* 为单个 ToolResult。"""

    name = "query_class"
    description = "班级维度分析：周趋势+峰值(trend)、聚类+散点(cluster)。"
    parameters = param_schema(
        properties={
            "mode": {
                "type": "string",
                "enum": list(VALID_MODES),
                "description": "trend=周趋势与峰值 | cluster=聚类与散点",
            },
        },
        required=["mode"],
    )
    tier = "L1"
    parallel_safe = True
    needs_feature_factory = True  # mode=cluster 需要 feature_factory

    def call(self, params, config, feature_factory=None, round_=None, parallel_group=None):
        """非法 mode 时返回 status=error，不抛异常。"""
        start = time.perf_counter()
        input_params = dict(params or {})
        mode = (input_params.get("mode") or "").strip().lower()
        if mode not in VALID_MODES:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return make_tool_result(
                tool=self.name,
                input_params=input_params,
                status="error",
                summary=f"无效 mode：{mode}，允许值：{', '.join(VALID_MODES)}",
                duration_ms=duration_ms,
                error=f"invalid mode: {mode}",
                round_=round_,
                parallel_group=parallel_group,
            )
        return super().call(params, config, feature_factory, round_, parallel_group)

    def perform(self, params, config, feature_factory=None):
        p = dict(params or {})
        mode = (p.get("mode") or "").strip().lower()

        if mode == "trend":
            # 全量周趋势（不传 student_ids）+ 峰值（默认 day=1）
            summary1, step1 = run_get_week_data({}, config, None)
            summary2, step2 = run_get_peak_data({"day": 1}, config, None)
        elif mode == "cluster":
            summary1, step1 = run_get_cluster_everyone({}, config, feature_factory)
            summary2, step2 = run_get_scatter({}, config, feature_factory)
        else:
            merged_summary = f"未知 mode: {mode}"
            step = {"tool": self.name, "params": p, "summary": merged_summary, "evidence": [], "visual_hints": []}
            return merged_summary, step

        return _merge_steps(summary1, step1, summary2, step2, self.name, p)

    def get_visual_hints(self, step_dict):
        return list(step_dict.get("visual_hints") or [])
