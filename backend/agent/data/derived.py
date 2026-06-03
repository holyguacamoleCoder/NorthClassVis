from __future__ import annotations

from pathlib import Path

import pandas as pd

from core import data_loader
from domain.features.calculators import FinalFeatureCalculator, PreliminaryFeatureCalculator
from services import week_service

from .loaders import load_student_info, load_submit_records, project_data_dir, validate_classes


def build_submit_record_joined(
    classes: list[str],
    majors: list[str] | None = None,
    *,
    data_dir: Path | None = None,
) -> pd.DataFrame:
    """submit + title（left join title_ID）；可选按 major 过滤学生。"""
    validate_classes(classes, data_dir)
    submit_df = load_submit_records(classes, data_dir)
    if submit_df.empty:
        return submit_df

    merged = data_loader.merge_dataframes_or_files(
        left_df=submit_df,
        right_path=data_loader.TITLE_INFO_PATH,
        right_columns=["title_ID", "knowledge", "sub_knowledge"],
        on="title_ID",
    )

    student_df = load_student_info(data_dir)
    merged = data_loader.merge_dataframes_or_files(
        left_df=merged,
        right_df=student_df,
        on="student_ID",
        right_columns=["student_ID", "major", "sex", "age"],
    )
    if majors:
        merged = merged[merged["major"].isin(majors)]

    return data_loader.process_non_numeric_values(merged)


def build_week_aggregation(
    classes: list[str],
    majors: list[str] | None = None,
    student_ids: list[str] | None = None,
    week_range: list[int] | tuple[int, int] | None = None,
    *,
    data_dir: Path | None = None,
) -> pd.DataFrame:
    """与 WeekRoutes.week_analysis 同一特征管道，输出 series 形长表。"""
    df = build_submit_record_joined(classes, majors=majors, data_dir=data_dir)
    if df.empty:
        return _empty_week_series_df()

    start_date = df["time"].min()
    df = df.copy()
    df["week"] = df["time"].apply(
        lambda value: week_service.calculate_week_of_year(value, start_date=start_date)
    )

    if student_ids:
        df = df[df["student_ID"].isin(student_ids)]
    if df.empty:
        return _empty_week_series_df()

    if week_range is not None and len(week_range) >= 2:
        df = week_service.filter_to_week_range(df, int(week_range[0]), int(week_range[1]))
    else:
        df = week_service.filter_to_recent_weeks(df)

    if df.empty:
        return _empty_week_series_df()

    pre_calc = PreliminaryFeatureCalculator(df)
    final_calc = FinalFeatureCalculator(
        pre_calc.get_features(),
        ["student_ID", "week", "knowledge"],
    )
    return _final_scores_to_series_df(final_calc.get_result())


def _empty_week_series_df() -> pd.DataFrame:
    return pd.DataFrame(columns=["student_ID", "week_index", "peak_value", "direction"])


def _final_scores_to_series_df(final_scores: pd.DataFrame) -> pd.DataFrame:
    """将 pivot (student × week×knowledge) 转为 week_peak_trend 用的 series 列。"""
    if final_scores is None or final_scores.empty:
        return _empty_week_series_df()

    rows: list[dict] = []
    # columns 为 MultiIndex (week, knowledge) 或单层 knowledge（单周）
    if isinstance(final_scores.columns, pd.MultiIndex):
        col_weeks = final_scores.columns.get_level_values(0).unique()
        col_knowledge = final_scores.columns.get_level_values(1)
        for student_id, series_row in final_scores.iterrows():
            week_peaks: dict[int, float] = {}
            for week in sorted(col_weeks):
                values = [
                    float(series_row[(week, k)])
                    for k in col_knowledge
                    if (week, k) in final_scores.columns and pd.notna(series_row[(week, k)])
                ]
                week_peaks[int(week)] = max(values) if values else 0.0
            rows.extend(_week_peaks_to_rows(str(student_id), week_peaks))
    else:
        for student_id, series_row in final_scores.iterrows():
            week_peaks = {0: float(series_row.max()) if len(series_row) else 0.0}
            rows.extend(_week_peaks_to_rows(str(student_id), week_peaks))

    return pd.DataFrame(rows, columns=["student_ID", "week_index", "peak_value", "direction"])


def _week_peaks_to_rows(student_id: str, week_peaks: dict[int, float]) -> list[dict]:
    out: list[dict] = []
    prev_peak: float | None = None
    for week_index in sorted(week_peaks):
        peak_value = float(week_peaks[week_index])
        if prev_peak is None:
            direction = "flat"
        elif peak_value > prev_peak:
            direction = "up"
        elif peak_value < prev_peak:
            direction = "down"
        else:
            direction = "flat"
        out.append(
            {
                "student_ID": student_id,
                "week_index": int(week_index),
                "peak_value": peak_value,
                "direction": direction,
            }
        )
        prev_peak = peak_value
    return out
