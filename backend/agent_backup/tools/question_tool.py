# 厚工具：按主体「题目」聚合，mode 控制内部行为。

import time
from typing import Any, Dict

from agent.tools.base import BaseTool
from agent.tools.base import make_tool_result
from agent.tools.base import param_schema
from agent.tools.question import run_get_question_list
from agent.tools.question import run_get_question_distribution
from agent.tools.question import run_get_question_timeline


VALID_MODES = ("list", "timeline", "dist")


class QueryQuestionTool(BaseTool):
    """query_question：题目维度厚工具，mode=list|timeline|dist 分发到现有 run_*。"""

    name = "query_question"
    description = "题目维度分析：列表(list)、时间线(timeline)、得分分布(dist)。"
    parameters = param_schema(
        properties={
            "mode": {
                "type": "string",
                "enum": list(VALID_MODES),
                "description": "list=题目列表 | timeline=单题时间线 | dist=单题得分分布",
            },
            "knowledge": {"type": "string", "description": "可选，知识点；mode=list 时有意义"},
            "title_id": {"type": "string", "description": "可选；mode=timeline/dist 时必填"},
            "limit": {"type": "integer", "description": "可选，题目数量上限"},
        },
        required=["mode"],
    )
    tier = "L1"
    parallel_safe = True
    needs_feature_factory = False

    def call(self, params, config, feature_factory=None, round_=None, parallel_group=None):
        """非法 mode 或 timeline/dist 缺少 title_id 时返回 status=error，不抛异常。"""
        start = time.perf_counter()
        input_params = dict(params or {})
        mode = (input_params.get("mode") or "").strip().lower()
        title_id = input_params.get("title_id")
        if isinstance(title_id, str):
            title_id = title_id.strip() or None
        elif title_id is not None:
            title_id = str(title_id).strip() or None

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
        if mode in ("timeline", "dist") and not title_id:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return make_tool_result(
                tool=self.name,
                input_params=input_params,
                status="error",
                summary=f"mode={mode} 需要提供 title_id",
                duration_ms=duration_ms,
                error="missing title_id",
                round_=round_,
                parallel_group=parallel_group,
            )
        return super().call(params, config, feature_factory, round_, parallel_group)

    def perform(self, params, config, feature_factory=None):
        p = dict(params or {})
        mode = (p.get("mode") or "").strip().lower()
        knowledge = p.get("knowledge")
        title_id = p.get("title_id")
        limit = p.get("limit")

        if mode == "list":
            executor_params = {"knowledge": knowledge, "title_id": title_id, "limit": limit}
            summary, step = run_get_question_list(executor_params, config, None)
        elif mode == "timeline":
            executor_params = {"title_id": title_id}
            summary, step = run_get_question_timeline(executor_params, config, None)
        elif mode == "dist":
            executor_params = {"title_id": title_id}
            summary, step = run_get_question_distribution(executor_params, config, None)
        else:
            summary = f"未知 mode: {mode}"
            step = {"tool": self.name, "params": p, "summary": summary}

        step["tool"] = self.name
        step["params"] = p
        return summary, step

    def get_visual_hints(self, step_dict):
        params = step_dict.get("params") or {}
        if params.get("knowledge"):
            return [{"view": "QuestionView", "params": {"knowledge": params["knowledge"]}}]
        if params.get("title_id"):
            return [{"view": "QuestionView", "params": {"title_id": params["title_id"]}}]
        return []
