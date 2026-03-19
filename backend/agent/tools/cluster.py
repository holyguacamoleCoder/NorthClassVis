# 工具层：聚类散点与每人聚类归属。

from typing import Any, Dict, Optional, Tuple

from agent.tools.base import BaseTool
from agent.tools.base import param_schema


def run_get_scatter(
    params: Dict[str, Any],
    config: Any,
    feature_factory: Any,
) -> Tuple[str, Dict[str, Any]]:
    """聚类散点。"""
    if feature_factory is None:
        return "需要特征工厂", {"tool": "get_scatter", "params": {}, "summary": "需要特征工厂", "coverage": {"covered": False, "reason": "样本不足"}}
    try:
        transformed = feature_factory.dim_reduction.get_transformed_data()
        student_clusters = feature_factory.cluster_analysis.get_student_clusters()
        n = len(student_clusters)
        summary = f"散点/聚类共 {n} 人"
        step = {"tool": "get_scatter", "params": {}, "summary": summary}
        step["coverage"] = {"covered": True} if n else {"covered": False, "reason": "样本不足"}
        return summary, step
    except Exception as e:
        summary = f"散点计算异常: {e}"
        return summary, {"tool": "get_scatter", "params": {}, "summary": summary, "coverage": {"covered": False, "reason": "样本不足"}}


def run_get_cluster_everyone(
    params: Dict[str, Any],
    config: Any,
    feature_factory: Any,
) -> Tuple[str, Dict[str, Any]]:
    """每人所属 cluster。"""
    if feature_factory is None:
        return "需要特征工厂", {"tool": "get_cluster_everyone", "params": {}, "summary": "需要特征工厂", "coverage": {"covered": False, "reason": "样本不足"}}
    try:
        student_clusters = feature_factory.cluster_analysis.get_student_clusters()
        n = len(student_clusters)
        summary = f"聚类结果共 {n} 人"
        step = {"tool": "get_cluster_everyone", "params": {}, "summary": summary}
        step["coverage"] = {"covered": True} if n else {"covered": False, "reason": "样本不足"}
        return summary, step
    except Exception as e:
        summary = f"聚类异常: {e}"
        return summary, {"tool": "get_cluster_everyone", "params": {}, "summary": summary, "coverage": {"covered": False, "reason": "样本不足"}}


class GetScatterTool(BaseTool):
    name = "get_scatter"
    description = "获取聚类散点数据。"
    parameters = param_schema({})
    tier = "L3"
    parallel_safe = True
    needs_feature_factory = True

    def perform(self, params, config, feature_factory=None):
        summary, step = run_get_scatter(params or {}, config, feature_factory)
        step["tool"] = self.name
        step["params"] = dict(params or {})
        return summary, step


class GetClusterEveryoneTool(BaseTool):
    name = "get_cluster_everyone"
    description = "获取每人所属 cluster。"
    parameters = param_schema({})
    tier = "L3"
    parallel_safe = True
    needs_feature_factory = True

    def perform(self, params, config, feature_factory=None):
        summary, step = run_get_cluster_everyone(params or {}, config, feature_factory)
        step["tool"] = self.name
        step["params"] = dict(params or {})
        return summary, step
