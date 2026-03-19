# 工具层：题目列表与单题详情。

from typing import Any, Dict, Optional, Tuple

from services import question_service

from agent.tools.base import BaseTool
from agent.tools.base import param_schema


def run_get_question_list(
    params: Dict[str, Any],
    config: Any,
    feature_factory: Any = None,
) -> Tuple[str, Dict[str, Any]]:
    """题目列表：按 knowledge / title_id / limit。"""
    df = config.get_submissions_with_knowledge_df()
    if df is None:
        return "题目数据加载失败", {"tool": "get_question_list", "params": dict(params or {}), "summary": "数据加载失败"}
    p = params or {}
    knowledge = p.get("knowledge")
    title_id = p.get("title_id") or p.get("titleID")
    limit = p.get("limit")
    if title_id is not None:
        rows = df[df["title_ID"].astype(str) == str(title_id)][["title_ID", "knowledge"]].drop_duplicates()
        if rows.empty:
            return "未找到该题目", {"tool": "get_question_list", "params": dict(p), "summary": "未找到该题目"}
        row = rows.iloc[0]
        payload = {
            "title_id": row["title_ID"],
            "knowledge": row["knowledge"],
            "timeline": question_service.process_timeline_data(df, row["title_ID"]),
            "distribution": question_service.process_distribution_data(df, row["title_ID"]),
            "avg_score": question_service.get_avg_score(df, row["title_ID"]),
            "sum_submit": question_service.get_sum_submit(df, row["title_ID"]),
        }
        summary = f"单题: {payload.get('knowledge')}，均分 {payload.get('avg_score'):.2f}，提交 {int(payload.get('sum_submit'))} 次"
        step = {"tool": "get_question_list", "params": dict(p), "summary": summary}
        step["raw"] = {"title_id": row["title_ID"], "knowledge": payload.get("knowledge"), "avg_score": payload.get("avg_score"), "sum_submit": payload.get("sum_submit")}
        step["evidence"] = [{"tool": "get_question_list", "summary": summary}]
        if payload.get("knowledge"):
            step["visual_hints"] = [{"view": "QuestionView", "params": {"knowledge": payload["knowledge"]}}]
        return summary, step
    if knowledge is not None:
        titles_data = question_service.get_titles_data_by_knowledge(df, knowledge, limit)
    else:
        titles_data = question_service.get_all_titles_data(df, limit)
    if not titles_data:
        return "无题目数据", {"tool": "get_question_list", "params": dict(p), "summary": "无题目数据"}
    avg_all = sum(t.get("avg_score", 0) for t in titles_data) / len(titles_data)
    below_avg = [t for t in titles_data if t.get("avg_score", 0) < avg_all]
    below_avg_list = [
        {"knowledge": t.get("knowledge"), "title_id": t.get("title_id"), "avg_score": round(t.get("avg_score", 0), 2)}
        for t in below_avg[:10]
    ]
    summary = f"题目数 {len(titles_data)}，平均分约 {avg_all:.2f}；低于均值的题目 {len(below_avg)} 道"
    if below_avg_list:
        summary += "（如：" + "、".join([str(x.get("knowledge") or x.get("title_id") or "") for x in below_avg_list[:3]]) + "）"
    step = {"tool": "get_question_list", "params": dict(p), "summary": summary}
    step["raw"] = {"count": len(titles_data), "avg_score": round(avg_all, 2), "below_avg_count": len(below_avg), "below_avg_list": below_avg_list}
    step["evidence"] = [{"tool": "get_question_list", "summary": summary}]
    if p.get("knowledge"):
        step["visual_hints"] = [{"view": "QuestionView", "params": {"knowledge": p["knowledge"]}}]
    return summary, step


def run_get_question_timeline(
    params: Dict[str, Any],
    config: Any,
    feature_factory: Any = None,
) -> Tuple[str, Dict[str, Any]]:
    """题目时间线。"""
    df = config.get_submissions_with_knowledge_df()
    if df is None:
        return "数据加载失败", {"tool": "get_question_timeline", "params": dict(params or {}), "summary": "数据加载失败"}
    title_id = (params or {}).get("title_id") or (params or {}).get("titleID")
    if not title_id:
        return "缺少 title_id", {"tool": "get_question_timeline", "params": dict(params or {}), "summary": "缺少 title_id"}
    timeline = question_service.process_timeline_data(df, title_id)
    n = len(timeline) if isinstance(timeline, list) else 0
    summary = f"时间线 {n} 个日期"
    return summary, {"tool": "get_question_timeline", "params": {"title_id": str(title_id)}, "summary": summary}


def run_get_question_distribution(
    params: Dict[str, Any],
    config: Any,
    feature_factory: Any = None,
) -> Tuple[str, Dict[str, Any]]:
    """题目得分分布。"""
    df = config.get_submissions_with_knowledge_df()
    if df is None:
        return "数据加载失败", {"tool": "get_question_distribution", "params": dict(params or {}), "summary": "数据加载失败"}
    title_id = (params or {}).get("title_id") or (params or {}).get("titleID")
    if not title_id:
        return "缺少 title_id", {"tool": "get_question_distribution", "params": dict(params or {}), "summary": "缺少 title_id"}
    dist = question_service.process_distribution_data(df, title_id)
    n = len(dist) if isinstance(dist, list) else 0
    summary = f"得分分布 {n} 档"
    return summary, {"tool": "get_question_distribution", "params": {"title_id": str(title_id)}, "summary": summary}


class ListQuestionsTool(BaseTool):
    name = "list_questions"
    description = "获取题目列表：按知识点或单题ID查询，返回题目数、平均分、低于均值的题目等摘要；用于回答某知识点掌握情况。"
    parameters = param_schema(
        {
            "topic": {"type": "string", "description": "可选，知识点（可与 resolve_knowledge 结果一致）"},
            "title_id": {"type": "string", "description": "可选，单题ID"},
            "limit": {"type": "integer", "description": "可选，题目数量上限"},
        },
        [],
    )
    tier = "L1"
    parallel_safe = True
    needs_feature_factory = False

    def perform(self, params, config, feature_factory=None):
        p = dict(params or {})
        executor_params = {
            "knowledge": p.get("topic") or p.get("knowledge"),
            "title_id": p.get("title_id"),
            "limit": p.get("limit"),
        }
        summary, step = run_get_question_list(executor_params, config, None)
        step["tool"] = self.name
        step["params"] = dict(params or {})
        return summary, step

    def get_visual_hints(self, step_dict):
        params = step_dict.get("params") or {}
        if params.get("knowledge"):
            return [{"view": "QuestionView", "params": {"knowledge": params["knowledge"]}}]
        return []


class GetQuestionTimelineTool(BaseTool):
    name = "get_question_timeline"
    description = "获取指定题目的时间线。"
    parameters = param_schema({"title_id": {"type": "string"}}, ["title_id"])
    tier = "L3"
    parallel_safe = True
    needs_feature_factory = False

    def perform(self, params, config, feature_factory=None):
        p = dict(params or {})
        executor_params = {"title_id": p.get("title_id") or p.get("titleID")}
        summary, step = run_get_question_timeline(executor_params, config, None)
        step["tool"] = self.name
        step["params"] = dict(params or {})
        return summary, step


class GetQuestionDistributionTool(BaseTool):
    name = "get_question_distribution"
    description = "获取指定题目的得分分布。"
    parameters = param_schema({"title_id": {"type": "string"}}, ["title_id"])
    tier = "L3"
    parallel_safe = True
    needs_feature_factory = False

    def perform(self, params, config, feature_factory=None):
        p = dict(params or {})
        executor_params = {"title_id": p.get("title_id") or p.get("titleID")}
        summary, step = run_get_question_distribution(executor_params, config, None)
        step["tool"] = self.name
        step["params"] = dict(params or {})
        return summary, step
