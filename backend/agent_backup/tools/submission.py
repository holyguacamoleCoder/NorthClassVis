# 工具层：提交记录。

from typing import Any, Dict, Optional, Tuple

from agent.tools._utils import ensure_list
from agent.tools.base import BaseTool
from agent.tools.base import param_schema


def run_get_student_submissions(
    params: Dict[str, Any],
    config: Any,
    feature_factory: Any = None,
) -> Tuple[str, Dict[str, Any]]:
    """提交记录，按 studentID / titleID / limit 过滤。"""
    df = config.get_submissions_df()
    if df is None:
        return "提交数据加载失败", {"tool": "get_student_submissions", "params": dict(params or {}), "summary": "数据加载失败", "coverage": {"covered": False, "reason": "样本不足"}}
    df = df.copy()
    p = params or {}
    student_id = p.get("studentID") or p.get("student_id")
    title_id = p.get("titleID") or p.get("title_id")
    limit = p.get("limit")
    if student_id:
        df = df[df["student_ID"].astype(str) == str(student_id)]
    if title_id:
        df = df[df["title_ID"].astype(str) == str(title_id)]
    if limit is not None:
        try:
            df = df.head(int(limit))
        except (TypeError, ValueError):
            pass
    n = len(df)
    summary = f"提交记录 {n} 条"
    step = {"tool": "get_student_submissions", "params": dict(p), "summary": summary}
    step["raw"] = {"count": n}
    step["evidence"] = [{"tool": "get_student_submissions", "summary": summary}]
    step["coverage"] = {"covered": True} if n else {"covered": False, "reason": "样本不足"}
    return summary, step


class QuerySubmissionsTool(BaseTool):
    name = "query_submissions"
    description = "按学生或题目查询提交记录摘要。"
    parameters = param_schema(
        {
            "student_id": {"type": "string", "description": "可选"},
            "title_id": {"type": "string", "description": "可选"},
            "limit": {"type": "integer", "description": "可选"},
        },
        [],
    )
    tier = "L2"
    parallel_safe = True
    needs_feature_factory = False

    def perform(self, params, config, feature_factory=None):
        p = dict(params or {})
        executor_params = {
            "studentID": p.get("student_id"),
            "titleID": p.get("title_id"),
            "limit": p.get("limit"),
        }
        summary, step = run_get_student_submissions(executor_params, config, None)
        step["tool"] = self.name
        step["params"] = dict(params or {})
        return summary, step
