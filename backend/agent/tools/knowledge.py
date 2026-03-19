# 工具层：知识点解析。

from typing import Any, Dict, Optional, Tuple

from agent.tools.base import BaseTool
from agent.tools.base import param_schema


def run_get_knowledge_points(
    params: Dict[str, Any],
    config: Any,
    feature_factory: Any = None,
) -> Tuple[str, Dict[str, Any]]:
    """知识点列表，可选 q 做模糊匹配。"""
    df = config.get_submissions_with_knowledge_df()
    if df is None or df.empty or "knowledge" not in df.columns:
        return "无知识点数据", {"tool": "get_knowledge_points", "params": dict(params), "summary": "无知识点数据"}
    knowledge_list = df["knowledge"].dropna().unique().tolist()
    knowledge_list = [str(k).strip() for k in knowledge_list if str(k).strip()]
    q = (params or {}).get("q") or (params or {}).get("keyword")
    if q:
        q = str(q).strip()
        knowledge_list = [k for k in knowledge_list if q in k]
    summary = f"知识点共 {len(knowledge_list)} 个" + (
        f"，匹配「{q}」: {knowledge_list[:10]}" if q and knowledge_list else f": {knowledge_list[:15]}"
    )
    step = {"tool": "get_knowledge_points", "params": dict(params or {}), "summary": summary}
    if knowledge_list:
        step["matched_knowledge"] = knowledge_list
    return summary, step


class ResolveKnowledgeTool(BaseTool):
    name = "resolve_knowledge"
    description = "解析用户说的知识点：返回知识点列表或按关键词模糊匹配（如用户说「链表」「递归」时先调用此工具得到 knowledge 再查题目）。"
    parameters = param_schema(
        {"topic": {"type": "string", "description": "可选，用户说的关键词，如「链表」「递归」"}},
        [],
    )
    tier = "L1"
    parallel_safe = True
    needs_feature_factory = False

    def perform(self, params, config, feature_factory=None):
        p = dict(params or {})
        q = p.get("topic") or p.get("q") or p.get("keyword")
        executor_params = {"q": q} if q else {}
        summary, step = run_get_knowledge_points(executor_params, config, None)
        step["tool"] = self.name
        step["params"] = dict(params or {})
        return summary, step

    def get_visual_hints(self, step_dict):
        matched = step_dict.get("matched_knowledge") or []
        k = matched[0] if matched else None
        if k:
            return [{"view": "QuestionView", "params": {"knowledge": k}}]
        return []
