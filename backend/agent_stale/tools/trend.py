# 工具层：周趋势与峰值。

from typing import Any, Dict, List, Optional, Tuple

from domain.features.calculators import FinalFeatureCalculator, PreliminaryFeatureCalculator
from services import week_service

from agent.tools._utils import ensure_list
from agent.tools.base import BaseTool
from agent.tools.base import param_schema


def _week_trend_summary(students: List[Dict[str, Any]], detail_level: int = 0) -> Tuple[str, Dict[str, Any]]:
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

    class_delta_ratio = None
    if avg_prev > 0:
        class_delta_ratio = (avg_recent - avg_prev) / avg_prev

    if class_delta_ratio is not None:
        if class_delta_ratio > 0.02:
            trend = "up"
            trend_text = "较前两周略升"
        elif class_delta_ratio < -0.02:
            trend = "down"
            trend_text = "较前两周略降"
        else:
            trend = "flat"
            trend_text = "较前两周基本持平"
    else:
        trend = "flat"
        trend_text = "较前两周基本持平"

    # 知识点 delta 需要用到“最近两周 vs 前两周”的均分对比；
    # 同时对输出做 TopK 截断，避免 raw 过大导致 LLM 解析困难。
    delta_threshold = 0.05  # 与旧版略升/略降规则保持一致
    detail_flag = int(detail_level or 0) >= 1
    max_knowledge_points = 25 if detail_flag else 10
    max_knowledge_summary = 6 if detail_flag else 3
    include_risk_detail = detail_flag
    risk_top_n = 5 if include_risk_detail else 3
    max_weak_knowledge_per_risk = 8 if include_risk_detail else 5

    knowledge_stats: List[Dict[str, Any]] = []
    all_knowledges = set()
    for s in students:
        for w in (s.get("weeks") or []):
            all_knowledges.update((w.get("scores") or {}).keys())
    for k in all_knowledges:
        t_recent, n_recent = 0.0, 0
        t_prev, n_prev = 0.0, 0
        for s in students:
            for w in (s.get("weeks") or []):
                scores = w.get("scores") or {}
                if k not in scores:
                    continue
                v = float(scores[k])
                if w.get("week") in recent_two:
                    t_recent += v
                    n_recent += 1
                if prev_two and w.get("week") in prev_two:
                    t_prev += v
                    n_prev += 1

        a_recent = (t_recent / n_recent) if n_recent else None
        a_prev = (t_prev / n_prev) if n_prev else None

        delta_ratio = None
        trend_label = None
        if a_recent is not None and a_prev is not None:
            if a_prev != 0:
                delta_ratio = (a_recent - a_prev) / a_prev
                if delta_ratio > delta_threshold:
                    trend_label = "略升"
                elif delta_ratio < -delta_threshold:
                    trend_label = "略降"
                else:
                    trend_label = "持平"
            else:
                trend_label = "prev为0"

        knowledge_stats.append(
            {
                "knowledge": k,
                "avg_recent": a_recent,
                "avg_prev": a_prev,
                "delta_ratio": delta_ratio,
                "n_recent": n_recent,
                "n_prev": n_prev,
                "trend_label": trend_label,
            }
        )

    # 用 abs(delta_ratio) 排序，只保留 topN（delta_ratio 为空的项先丢弃）。
    knowledge_stats_with_ratio = [x for x in knowledge_stats if x.get("delta_ratio") is not None]
    knowledge_stats_with_ratio.sort(key=lambda x: abs(float(x.get("delta_ratio") or 0.0)), reverse=True)
    top_knowledge_stats = knowledge_stats_with_ratio[:max_knowledge_points]

    # 给 summary 提供更精细的数值（便于 LLM 生成“精确结论/排名”），但仍然做截断。
    def _fmt_float(v: Any, ndigits: int = 3) -> str:
        try:
            return f"{float(v):.{ndigits}f}"
        except Exception:
            return str(v)

    knowledge_summary = []
    for x in top_knowledge_stats[:max_knowledge_summary]:
        k = x.get("knowledge")
        a_recent = x.get("avg_recent")
        a_prev = x.get("avg_prev")
        dr = x.get("delta_ratio")
        try:
            dr_pct = float(dr) * 100.0
            knowledge_summary.append(f"{k}：{_fmt_float(a_prev)}->{_fmt_float(a_recent)}（Δ{dr_pct:+.1f}%）")
        except Exception:
            knowledge_summary.append(f"{k}：略有变化（需查看 raw 数值）")

    risk_records: List[Dict[str, Any]] = []
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
                drop_ratio = (a_rec - a_prev) / a_prev
                risk_records.append(
                    {
                        "id": s.get("id"),
                        "avg_prev": a_prev,
                        "avg_recent": a_rec,
                        "drop_ratio": drop_ratio,
                    }
                )

    risk_records.sort(key=lambda x: float(x.get("drop_ratio") or 0.0))
    risk_count = len(risk_records)
    risk_students_top = risk_records[:risk_top_n]
    risk_students_detail: List[Dict[str, Any]] = []
    if include_risk_detail and risk_students_top:
        # 对每个风险学生，进一步给出其“薄弱知识点”的最近/前置对比，便于生成精细建议。
        student_by_id = {s.get("id"): s for s in students}
        for rec in risk_students_top:
            sid = rec.get("id")
            sdata = student_by_id.get(sid)
            if not sdata:
                continue
            student_weeks = sdata.get("weeks") or []
            all_knowledges = set()
            for w in student_weeks:
                all_knowledges.update((w.get("scores") or {}).keys())

            kstats: List[Dict[str, Any]] = []
            for k in all_knowledges:
                t_recent, n_recent = 0.0, 0
                t_prev, n_prev = 0.0, 0
                for w in student_weeks:
                    wk = w.get("week")
                    scores = w.get("scores") or {}
                    if k not in scores:
                        continue
                    v = float(scores[k])
                    if wk in recent_two:
                        t_recent += v
                        n_recent += 1
                    if prev_two and wk in prev_two:
                        t_prev += v
                        n_prev += 1

                a_recent = (t_recent / n_recent) if n_recent else None
                a_prev = (t_prev / n_prev) if n_prev else None
                if a_recent is None or a_prev is None or a_prev == 0:
                    continue
                delta_ratio = (a_recent - a_prev) / a_prev
                kstats.append(
                    {
                        "knowledge": k,
                        "avg_prev": a_prev,
                        "avg_recent": a_recent,
                        "delta_ratio": delta_ratio,
                        "n_prev": n_prev,
                        "n_recent": n_recent,
                    }
                )

            # 薄弱知识：优先最近均分最低，其次考虑下滑幅度更大
            kstats.sort(
                key=lambda x: (
                    float(x.get("avg_recent") or 0.0),
                    float(x.get("delta_ratio") or 0.0),
                )
            )
            risk_students_detail.append({"id": sid, "weak_knowledge": kstats[:max_weak_knowledge_per_risk]})

    summary_parts = [f"学生数 {len(students)}，周数约 {len(sorted_weeks)}", trend_text]
    if knowledge_summary:
        summary_parts.append("按知识点：" + "；".join(knowledge_summary[:3]))
    if risk_count > 0:
        summary_parts.append(f"波动较大学生约 {risk_count} 人")
    out = {
        "trend": trend,
        "class_delta_ratio": class_delta_ratio,
        "weeks_count": len(sorted_weeks),
        "recent_two_weeks": recent_two,
        "prev_two_weeks": prev_two,
        "knowledge_summary": knowledge_summary,
        "knowledge_stats": top_knowledge_stats,
        "risk_count": risk_count,
        "risk_students_top": risk_students_top,
    }
    if include_risk_detail:
        out["risk_students_detail"] = risk_students_detail
    return "；".join(summary_parts), out


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
    wr = config.get_week_range() if hasattr(config, "get_week_range") else None
    df = week_service.filter_to_week_range(df, wr[0], wr[1]) if wr else week_service.filter_to_recent_weeks(df)
    if df.empty:
        return "周范围筛选后无数据", {
            "tool": "get_week_data",
            "params": dict(params or {}),
            "summary": "周范围筛选后无数据",
            "coverage": {"covered": False, "reason": "样本不足"},
        }
    pre_calculator = PreliminaryFeatureCalculator(df)
    pre_df = pre_calculator.get_features()
    final_calculator = FinalFeatureCalculator(pre_df, ["student_ID", "week", "knowledge"])
    final_result = final_calculator.calc_final_features()
    result = final_result.to_dict(orient="index")
    payload = week_service.week_scores_to_chart_payload(result)
    students = payload.get("students") or []
    detail_level = 0
    try:
        detail_level = int((params or {}).get("detail_level") or 0)
    except Exception:
        detail_level = 0
    summary, trend_info = _week_trend_summary(students, detail_level=detail_level)
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
    detail_level = 0
    try:
        detail_level = int((params or {}).get("detail_level") or 0)
    except Exception:
        detail_level = 0
    if day is None or not (1 <= int(day) <= 7):
        return "day 需为 1～7", {"tool": "get_peak_data", "params": dict(p), "summary": "day 需为 1～7", "coverage": {"covered": False, "reason": "参数无效"}}
    if student_ids:
        df = df[df["student_ID"].isin(student_ids)]
    result = week_service.calculate_peak_data(df, int(day))
    peaks = result.get("peaks") or []
    max_peaks = 30 if detail_level >= 1 else 10
    peaks_cut = list(peaks)[:max_peaks]
    summary = f"峰值数据 {len(peaks)} 人"
    step = {"tool": "get_peak_data", "params": dict(p), "summary": summary}
    step["coverage"] = {"covered": True} if peaks else {"covered": False, "reason": "样本不足"}
    step["raw"] = {"peaks_total": len(peaks), "day": int(day), "peaks": peaks_cut}
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
