from datetime import datetime

import pandas as pd


def _normalize_to_timestamp(value):
    if isinstance(value, (pd.Timestamp, datetime)):
        return value
    return pd.to_datetime(value, unit="s")


def calculate_week_of_year(timestamp, start_date=None):
    timestamp_value = _normalize_to_timestamp(timestamp)
    start_value = _normalize_to_timestamp(start_date) if start_date is not None else timestamp_value
    delta = (timestamp_value - start_value).days // 7
    return delta


def week_scores_to_chart_payload(data):
    students = []

    for student_id, weekly_scores in data.items():
        if not weekly_scores:
            students.append({"id": student_id, "weeks": []})
            continue

        all_weeks = [week for week, _ in weekly_scores.keys()]
        all_knowledge_points = {knowledge for _, knowledge in weekly_scores.keys()}
        weeks = []

        for week_number in range(min(all_weeks), max(all_weeks) + 1):
            scores = {
                knowledge: weekly_scores.get((week_number, knowledge), 0.0)
                for knowledge in all_knowledge_points
            }
            weeks.append({"week": week_number, "scores": scores})

        students.append({"id": student_id, "weeks": weeks})

    return {"students": students}


def calculate_peak_data(df, day):
    peak_df = df.copy()
    peak_df["time"] = pd.to_datetime(peak_df["time"], unit="s")
    start_date = peak_df["time"].min()
    peak_df["week"] = peak_df["time"].apply(lambda value: calculate_week_of_year(value, start_date=start_date))
    peak_df["weekday"] = peak_df["time"].dt.weekday
    peak_df["period"] = peak_df["weekday"].apply(
        lambda value: "Mon_to_Day" if value <= day else "after_Day_to_Sun"
    )

    grouped = peak_df.groupby(["student_ID", "week", "period"]).size().reset_index(name="count")
    pivoted = grouped.pivot_table(
        index=["student_ID", "week"],
        columns="period",
        values="count",
        fill_value=0,
        aggfunc="sum",
    ).reindex(columns=["Mon_to_Day", "after_Day_to_Sun"], fill_value=0)

    result_list = []
    for student_id, group in pivoted.groupby(level="student_ID"):
        weeks = []
        for week_num in group.index.get_level_values("week").unique():
            row = group.xs(week_num, level="week")
            weeks.append(
                {
                    "week": week_num,
                    "Mon_to_Day": int(row["Mon_to_Day"].iloc[0]),
                    "after_Day_to_Sun": int(row["after_Day_to_Sun"].iloc[0]),
                }
            )
        result_list.append({"id": student_id, "weeks": weeks})

    return {"peaks": result_list}


def transform_data_for_visualization(data):
    return week_scores_to_chart_payload(data)
