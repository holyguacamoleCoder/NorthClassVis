# 工具层：学生树与学情画像。

from typing import Any, Dict, List, Optional, Tuple

from core import data_loader
from services import student_service

from agent.tools._utils import ensure_list
from agent.tools.base import BaseTool
from agent.tools.base import param_schema


def run_get_student_tree(
    params: Dict[str, Any],
    config: Any,
    feature_factory: Any = None,
) -> Tuple[str, Dict[str, Any]]:
    """学生树结构。"""
    df = config.get_submissions_df()
    if df is None:
        return "数据加载失败", {"tool": "get_student_tree", "params": dict(params or {}), "summary": "数据加载失败", "coverage": {"covered": False, "reason": "样本不足"}}
    p = params or {}
    student_ids = ensure_list(p.get("student_ids") or p.get("student_ids[]"))
    limit = p.get("limit")
    if student_ids:
        df = df[df["student_ID"].isin(student_ids)]
    student_info = data_loader.load_data(data_loader.STUDENT_INFO_PATH)
    if student_info is None:
        return "学生信息加载失败", {"tool": "get_student_tree", "params": dict(p), "summary": "学生信息加载失败", "coverage": {"covered": False, "reason": "样本不足"}}
    tree_data = student_service.build_student_tree(df, student_info)
    children = tree_data.get("children") or []
    if limit is not None:
        try:
            children = children[: int(limit)]
        except (TypeError, ValueError):
            pass
        tree_data = {"name": tree_data.get("name", "Root"), "children": children}
    n_nodes = len(children)
    summary = f"学生树根下 {n_nodes} 个学生节点"
    step = {"tool": "get_student_tree", "params": dict(p), "summary": summary}
    step["raw"] = {"nodes_count": n_nodes}
    step["evidence"] = [{"tool": "get_student_tree", "summary": summary}]
    step["coverage"] = {"covered": True} if n_nodes else {"covered": False, "reason": "样本不足"}
    if student_ids:
        step["visual_hints"] = [{"view": "StudentView", "params": {"student_ids": student_ids}}]
    return summary, step


def run_get_cluster_display(
    params: Dict[str, Any],
    config: Any,
    feature_factory: Any,
) -> Tuple[str, Dict[str, Any]]:
    """指定学生画像；增强 summary 为薄弱点/建议型摘要供 LLM 推理。"""
    if feature_factory is None:
        return "需要特征工厂", {"tool": "get_cluster_display", "params": dict(params or {}), "summary": "需要特征工厂", "coverage": {"covered": False, "reason": "样本不足"}}
    student_ids = ensure_list((params or {}).get("student_ids") or (params or {}).get("student_ids[]"))
    if not student_ids:
        return "未提供 student_ids", {"tool": "get_cluster_display", "params": dict(params or {}), "summary": "未提供 student_ids", "coverage": {"covered": False, "reason": "样本不足"}}
    result = {}
    weak_per_student = []
    for sid in student_ids:
        try:
            knowledge = feature_factory.feature_knowledge.loc[sid].to_dict()
            bonus = feature_factory.feature_bonus.loc[sid].to_dict()
            result[sid] = {"knowledge": knowledge, "bonus": bonus}
            k_sorted = sorted([(k, float(v)) for k, v in knowledge.items() if v is not None], key=lambda x: x[1])
            if k_sorted:
                weak = [k for k, v in k_sorted[:3] if v < 0.5]
                if weak:
                    weak_per_student.append(f"学生{sid[:8]}…薄弱点：{','.join(weak[:3])}")
        except KeyError:
            result[sid] = {"error": f"未找到学生 {sid}"}
    summary = f"画像 {len(result)} 人"
    if weak_per_student:
        summary += "；" + "；".join(weak_per_student[:2]) + "。建议优先巩固上述薄弱知识点。"
    step = {"tool": "get_cluster_display", "params": {"student_ids": student_ids}, "summary": summary}
    step["raw"] = {"count": len(result), "student_ids": student_ids, "weak_summary": weak_per_student[:3]}
    step["evidence"] = [{"tool": "get_cluster_display", "summary": summary}]
    step["visual_hints"] = [{"view": "StudentView", "params": {"student_ids": student_ids}}]
    step["coverage"] = {"covered": True} if result else {"covered": False, "reason": "样本不足"}
    return summary, step


class GetStudentPortraitTool(BaseTool):
    name = "get_student_portrait"
    description = "获取指定学生的学情画像（知识点掌握、特征等）；用于学生个体诊断。"
    parameters = param_schema(
        {"student_ids": {"type": "array", "items": {"type": "string"}, "description": "学生ID列表"}},
        ["student_ids"],
    )
    tier = "L1"
    parallel_safe = True
    needs_feature_factory = True

    def perform(self, params, config, feature_factory=None):
        p = dict(params or {})
        student_ids = ensure_list(p.get("student_ids") or p.get("student_ids[]"))
        executor_params = {"student_ids": student_ids}
        summary, step = run_get_cluster_display(executor_params, config, feature_factory)
        step["tool"] = self.name
        step["params"] = dict(params or {})
        return summary, step

    def get_visual_hints(self, step_dict):
        params = step_dict.get("params") or {}
        if params.get("student_ids"):
            return [{"view": "StudentView", "params": {"student_ids": params["student_ids"]}}]
        return []


class GetStudentTreeTool(BaseTool):
    name = "get_student_tree"
    description = "获取学生树结构。"
    parameters = param_schema(
        {"student_ids": {"type": "array", "items": {"type": "string"}}, "limit": {"type": "integer"}},
        [],
    )
    tier = "L3"
    parallel_safe = True
    needs_feature_factory = False

    def perform(self, params, config, feature_factory=None):
        summary, step = run_get_student_tree(params or {}, config, None)
        step["tool"] = self.name
        step["params"] = dict(params or {})
        return summary, step
