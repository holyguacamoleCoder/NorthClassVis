# 厚工具：按主体「学生」聚合，mode 控制内部行为。

import time
from typing import Any, Dict, List

from agent.tools.base import BaseTool
from agent.tools.base import make_tool_result
from agent.tools.base import param_schema
from agent.tools.student import run_get_cluster_display
from agent.tools.student import run_get_student_tree
from agent.tools.submission import run_get_student_submissions
from agent.tools.trend import run_get_week_data
from agent.tools._utils import ensure_list


VALID_MODES = ("portrait", "tree", "trend", "detail")


class QueryStudentTool(BaseTool):
    """query_student：学生维度厚工具，mode=portrait|tree|trend|detail 分发到现有 run_*。"""

    name = "query_student"
    description = "学生维度分析：画像(portrait)、学习路径树(tree)、周趋势(trend)、提交明细(detail)。"
    parameters = param_schema(
        properties={
            "mode": {
                "type": "string",
                "enum": list(VALID_MODES),
                "description": "portrait=画像 | tree=学习路径树 | trend=周趋势 | detail=提交明细",
            },
            "student_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "可选，学生ID列表",
            },
        },
        required=["mode"],
    )
    tier = "L1"
    parallel_safe = True
    needs_feature_factory = True  # portrait 需要 feature_factory

    def call(self, params, config, feature_factory=None, round_=None, parallel_group=None):
        """非法 mode 时直接返回 status=error 的 ToolResult，不抛异常。"""
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
        student_ids = ensure_list(p.get("student_ids") or p.get("student_ids[]"))

        if mode == "portrait":
            executor_params = {"student_ids": student_ids}
            summary, step = run_get_cluster_display(executor_params, config, feature_factory)
        elif mode == "tree":
            executor_params = {"student_ids": student_ids, **{k: p[k] for k in ("limit",) if k in p}}
            summary, step = run_get_student_tree(executor_params, config, None)
        elif mode == "trend":
            executor_params = {"student_ids": student_ids}
            summary, step = run_get_week_data(executor_params, config, None)
        elif mode == "detail":
            # run_get_student_submissions 接受 studentID/student_id（单值）；多学生时传第一个或由上层拆分
            executor_params = {"limit": p.get("limit")}
            if student_ids:
                executor_params["studentID"] = student_ids[0]
            summary, step = run_get_student_submissions(executor_params, config, None)
        else:
            # 已在 call() 中拦截，此处不应到达
            summary = f"未知 mode: {mode}"
            step = {"tool": self.name, "params": p, "summary": summary}

        step["tool"] = self.name
        step["params"] = p
        return summary, step

    def get_visual_hints(self, step_dict):
        params = step_dict.get("params") or {}
        student_ids = params.get("student_ids")
        if student_ids:
            return [{"view": "StudentView", "params": {"student_ids": student_ids}}]
        if step_dict.get("tool") == "get_week_data" or (params.get("mode") == "trend"):
            return [{"view": "WeekView", "params": {"kind": 1}}]
        return []
