# 工具层：周趋势与峰值。

from typing import Any, Dict, List, Optional, Tuple

from domain.features.calculators import FinalFeatureCalculator, PreliminaryFeatureCalculator
from services import week_service

from agent.tools._utils import ensure_list
from agent.tools.base import BaseTool
from agent.tools.base import param_schema


def _week_trend_summary(students: List[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
    """从 students 的 weeks 计算最近两周 vs 前两周趋势、知识点摘要、风险学生数。"""
    if not students:
        return "无周数据", {"trend": "unknown", "knowledge_summary": [], "risk_count": 0}
    all_weeks = set()
    for s in students:
        for w in (s.get("weeks") or []):
            all_weeks.add(w.get("week"))
    if not all_weeks:
        return "无周数据", {"trend": "unknown", "knowledge_summary": [], "risk_count": 0}
    sorted_weeks = sorted(all_weeks)
    recent_two = sorted_weeks[-2:] if len(sorted_weeks) >= 2 else sorted_weeks[-1:]
    prev_two = sorted_weeks[-4:-2] if len(sorted_weeks) >= 4 else (sorted_weeks[-3:-2] if len(sorted_weeks) >= 3 else [])
    if not recent_two:
        return "无周数据", {"trend": "unknown", "knowledge_summary": [], "risk_count": 0}

    def _week_avg(week_list: List[Any]) -> float:
        total, n = 0.0, 0
        for s in students:
            for w in (s.get("weeks") or []):
                if w.get("week") not in week_list:
                    continue
                scores = w.get("scores") or {}
                for v in scores.values():
                    total += float(v)
                    n += 1
        return total / n if n else 0.0

    avg_recent = _week_avg(recent_two)
    avg_prev = _week_avg(prev_two) if prev_two else avg_recent
    if avg_prev > 0:
        delta = (avg_recent - avg_prev) / avg_prev
        if delta > 0.02:
            trend = "up"
            trend_text = "较前两周略升"
        elif delta < -0.02:
            trend = "down"
            trend_text = "较前两周略降"
        else:
            trend = "flat"
            trend_text = "较前两周基本持平"
    else:
        trend = "flat"
        trend_text = "较前两周基本持平"

    knowledge_deltas = {}
    all_knowledges = set()
    for s in students:
        for w in (s.get("weeks") or []):
            all_knowledges.update((w.get("scores") or {}).keys())
    for k in all_knowledges:
        t1, n1 = 0.0, 0
        t2, n2 = 0.0, 0
        for s in students:
            for w in (s.get("weeks") or []):
                scores = w.get("scores") or {}
                if k not in scores:
                    continue
                v = float(scores[k])
                if w.get("week") in recent_two:
                    t1 += v
                    n1 += 1
                if prev_two and w.get("week") in prev_two:
                    t2 += v
                    n2 += 1
        a1 = t1 / n1 if n1 else 0
        a2 = t2 / n2 if n2 else a1
        if a2 > 0 and (a1 - a2) / a2 < -0.05:
            knowledge_deltas[k] = "略降"
        elif a2 > 0 and (a1 - a2) / a2 > 0.05:
            knowledge_deltas[k] = "略升"
    knowledge_summary = [f"{k}：{v}" for k, v in list(knowledge_deltas.items())[:5]]

    risk_count = 0
    if prev_two and recent_two:
        for s in students:
            tot_prev, n_prev = 0.0, 0
            tot_rec, n_rec = 0.0, 0
            for w in (s.get("weeks") or []):
                wk = w.get("week")
                scores = (w.get("scores") or {}).values()
                for v in scores:
                    if wk in prev_two:
                        tot_prev += float(v)
                        n_prev += 1
                    if wk in recent_two:
                        tot_rec += float(v)
                        n_rec += 1
            a_prev = tot_prev / n_prev if n_prev else 0
            a_rec = tot_rec / n_rec if n_rec else 0
            if a_prev > 0 and (a_rec - a_prev) / a_prev < -0.1:
                risk_count += 1

    summary_parts = [f"学生数 {len(students)}，周数约 {len(sorted_weeks)}", trend_text]
    if knowledge_summary:
        summary_parts.append("按知识点：" + "；".join(knowledge_summary[:3]))
    if risk_count > 0:
        summary_parts.append(f"波动较大学生约 {risk_count} 人")
    return "；".join(summary_parts), {"trend": trend, "weeks_count": len(sorted_weeks), "knowledge_summary": knowledge_summary, "risk_count": risk_count}


def run_get_week_data(
    params: Dict[str, Any],
    config: Any,
    feature_factory: Any = None,
) -> Tuple[str, Dict[str, Any]]:
    """周趋势：与 week_routes.week_analysis 同逻辑；增强 summary/raw 供 LLM 推理。"""
    df = config.get_submissions_with_knowledge_df()
    if df is None or df.empty:
        return "无周数据", {"tool": "get_week_data", "params": dict(params or {}), "summary": "无周数据", "coverage": {"covered": False, "reason": "样本不足"}}
    df = df.copy()
    student_ids = ensure_list((params or {}).get("student_ids") or (params or {}).get("student_ids[]"))
    if student_ids:
        df = df[df["student_ID"].isin(student_ids)]
    if df.empty:
        return "筛选后无数据", {"tool": "get_week_data", "params": dict(params or {}), "summary": "筛选后无数据", "coverage": {"covered": False, "reason": "样本不足"}}
    start_date = df["time"].min()
    df["week"] = df["time"].apply(lambda v: week_service.calculate_week_of_year(v, start_date=start_date))
    df = week_service.filter_to_recent_weeks(df)
    pre_calculator = PreliminaryFeatureCalculator(df)
    pre_df = pre_calculator.get_features()
    final_calculator = FinalFeatureCalculator(pre_df, ["student_ID", "week", "knowledge"])
    final_result = final_calculator.calc_final_features()
    result = final_result.to_dict(orient="index")
    payload = week_service.week_scores_to_chart_payload(result)
    students = payload.get("students") or []
    summary, trend_info = _week_trend_summary(students)
    step = {"tool": "get_week_data", "params": dict(params or {}), "summary": summary}
    step["raw"] = {"students_count": len(students), **trend_info}
    step["evidence"] = [{"tool": "get_week_data", "summary": summary}]
    step["visual_hints"] = [{"view": "WeekView", "params": {"kind": 1}}]
    step["coverage"] = {"covered": True}
    return summary, step


def run_get_peak_data(
    params: Dict[str, Any],
    config: Any,
    feature_factory: Any = None,
) -> Tuple[str, Dict[str, Any]]:
    """前后半周提交峰值。"""
    df = config.get_submissions_with_knowledge_df()
    if df is None:
        return "数据加载失败", {"tool": "get_peak_data", "params": dict(params or {}), "summary": "数据加载失败", "coverage": {"covered": False, "reason": "样本不足"}}
    p = params or {}
    student_ids = ensure_list(p.get("student_ids") or p.get("student_ids[]"))
    day = p.get("day")
    if day is None or not (1 <= int(day) <= 7):
        return "day 需为 1～7", {"tool": "get_peak_data", "params": dict(p), "summary": "day 需为 1～7", "coverage": {"covered": False, "reason": "参数无效"}}
    if student_ids:
        df = df[df["student_ID"].isin(student_ids)]
    result = week_service.calculate_peak_data(df, int(day))
    peaks = result.get("peaks") or []
    summary = f"峰值数据 {len(peaks)} 人"
    step = {"tool": "get_peak_data", "params": dict(p), "summary": summary}
    step["coverage"] = {"covered": True} if peaks else {"covered": False, "reason": "样本不足"}
    return summary, step


class QueryWeeklyTrendTool(BaseTool):
    name = "query_weekly_trend"
    description = "查询周趋势：班级或指定学生按周的得分趋势；用于回答「本周/最近两周表现如何」。"
    parameters = param_schema(
        {"student_ids": {"type": "array", "items": {"type": "string"}, "description": "可选，学生ID列表；不传则全班"}},
        [],
    )
    tier = "L1"
    parallel_safe = True
    needs_feature_factory = False

    def perform(self, params, config, feature_factory=None):
        p = dict(params or {})
        executor_params = {"student_ids": p.get("student_ids")}
        summary, step = run_get_week_data(executor_params, config, None)
        step["tool"] = self.name
        step["params"] = dict(params or {})
        return summary, step

    def get_visual_hints(self, step_dict):
        return [{"view": "WeekView", "params": {"kind": 1}}]


class QueryPeakActivityTool(BaseTool):
    name = "query_peak_activity"
    description = "查询按日前半/后半的提交峰值。"
    parameters = param_schema(
        {"student_ids": {"type": "array", "items": {"type": "string"}}, "day": {"type": "integer", "description": "1～7"}},
        ["day"],
    )
    tier = "L2"
    parallel_safe = True
    needs_feature_factory = False

    def perform(self, params, config, feature_factory=None):
        p = dict(params or {})
        executor_params = {"student_ids": p.get("student_ids"), "day": p.get("day")}
        summary, step = run_get_peak_data(executor_params, config, None)
        step["tool"] = self.name
        step["params"] = dict(params or {})
        return summary, step
