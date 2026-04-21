# 厚工具：知识点维度，合并「解析 + 相关题目概况」为一次调用。

import time
from typing import Any, Dict, List

from agent.tools.base import BaseTool
from agent.tools.base import make_tool_result
from agent.tools.base import param_schema
from agent.tools.knowledge import run_get_knowledge_points
from agent.tools.question import run_get_question_list


class QueryKnowledgeTool(BaseTool):
    """query_knowledge：先解析知识点，再查相关题目，合并为单个 ToolResult。"""

    name = "query_knowledge"
    description = "知识点维度：解析知识点并返回相关题目概况（合并 resolve_knowledge + 题目列表）。"
    parameters = param_schema(
        properties={
            "knowledge": {
                "type": "string",
                "description": "必填，知识点名称",
            },
        },
        required=["knowledge"],
    )
    tier = "L1"
    parallel_safe = True
    needs_feature_factory = False

    def call(self, params, config, feature_factory=None, round_=None, parallel_group=None):
        """knowledge 为空时返回 status=error，不抛异常。"""
        start = time.perf_counter()
        input_params = dict(params or {})
        knowledge = input_params.get("knowledge")
        if knowledge is not None and isinstance(knowledge, str):
            knowledge = knowledge.strip()
        if not knowledge:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return make_tool_result(
                tool=self.name,
                input_params=input_params,
                status="error",
                summary="未提供 knowledge",
                duration_ms=duration_ms,
                error="missing knowledge",
                round_=round_,
                parallel_group=parallel_group,
            )
        return super().call(params, config, feature_factory, round_, parallel_group)

    def perform(self, params, config, feature_factory=None):
        p = dict(params or {})
        knowledge = (p.get("knowledge") or "").strip()

        # 1) 知识点解析（run_get_knowledge_points 即「resolve」逻辑）
        resolve_params = {"q": knowledge}
        summary1, step1 = run_get_knowledge_points(resolve_params, config, None)
        evidence1: List[Dict[str, Any]] = list(step1.get("evidence") or [])
        if not evidence1 and summary1:
            evidence1 = [{"tool": "get_knowledge_points", "summary": summary1}]

        # 2) 相关题目概况
        list_params = {"knowledge": knowledge}
        summary2, step2 = run_get_question_list(list_params, config, None)
        evidence2: List[Dict[str, Any]] = list(step2.get("evidence") or [])
        if not evidence2 and summary2:
            evidence2 = [{"tool": "get_question_list", "summary": summary2}]

        # 3) 合并 summary 与 evidence
        merged_summary = f"{summary1}；相关题目：{summary2}"
        merged_evidence = evidence1 + evidence2
        for e in merged_evidence:
            if isinstance(e, dict):
                e["tool"] = e.get("tool") or self.name

        raw = {
            "resolve": step1.get("raw"),
            "questions": step2.get("raw"),
        }
        visual_hints = list(step2.get("visual_hints") or [])
        if not visual_hints and step1.get("matched_knowledge"):
            k = step1["matched_knowledge"][0] if step1["matched_knowledge"] else knowledge
            visual_hints = [{"view": "QuestionView", "params": {"knowledge": k}}]
        if not visual_hints and knowledge:
            visual_hints = [{"view": "QuestionView", "params": {"knowledge": knowledge}}]

        step = {
            "tool": self.name,
            "params": p,
            "summary": merged_summary,
            "evidence": merged_evidence,
            "raw": raw,
            "visual_hints": visual_hints,
        }
        return merged_summary, step

    def get_visual_hints(self, step_dict):
        params = step_dict.get("params") or {}
        k = params.get("knowledge")
        if k:
            return [{"view": "QuestionView", "params": {"knowledge": k}}]
        return []
