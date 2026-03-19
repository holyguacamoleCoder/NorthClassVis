# 工具层：导航/元数据。

from typing import Any, Dict, Optional, Tuple

from agent.tools.base import BaseTool
from agent.tools.base import param_schema


def run_get_nav_filter(params, config, feature_factory=None):
    """当前可选班级与专业列表。"""
    classes = config.get_class_list() or []
    majors = config.get_majors() or []
    summary = f"当前班级: {classes}，专业: {majors}"
    return summary, {"tool": "get_nav_filter", "params": {}, "summary": summary}


class GetContextFilterTool(BaseTool):
    name = "get_context_filter"
    description = "获取当前可选的班级列表与专业列表，用于了解筛选上下文或元数据。"
    parameters = param_schema({})
    tier = "L1"
    parallel_safe = True
    needs_feature_factory = False

    def perform(self, params, config, feature_factory=None):
        summary, step = run_get_nav_filter({}, config, None)
        step["tool"] = self.name
        step["params"] = dict(params or {})
        return summary, step
