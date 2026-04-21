import pandas as pd


def _filter_by_title_id(merged_data, title_id):
    return merged_data[merged_data["title_ID"].astype(str) == str(title_id)].copy()


def _build_title_payload(merged_data, title_row):
    title_id = title_row["title_ID"]
    return {
        "title_id": title_id,
        "knowledge": title_row["knowledge"],
        "timeline": process_timeline_data(merged_data, title_id),
        "distribution": process_distribution_data(merged_data, title_id),
        "avg_score": get_avg_score(merged_data, title_id),
        "sum_submit": get_sum_submit(merged_data, title_id),
    }


def get_title_data_by_id(merged_data, title_id):
    title_rows = merged_data[
        merged_data["title_ID"].astype(str) == str(title_id)
    ][["title_ID", "knowledge"]].drop_duplicates()
    if title_rows.empty:
        return None
    title_row = title_rows.iloc[0]
    return _build_title_payload(merged_data, title_row)


def process_timeline_data(merged_data, title_id):
    timeline_data = _filter_by_title_id(merged_data, title_id)
    timeline_data["time"] = pd.to_datetime(timeline_data["time"], unit="s")
    timeline_data["date"] = timeline_data["time"].dt.date
    timeline_data = timeline_data.groupby(["date"]).agg({"score": "count"}).reset_index()
    timeline_data.columns = ["date", "submission_count"]
    timeline_data["date"] = timeline_data["date"].astype(str)
    return timeline_data.to_dict(orient="records")


def process_distribution_data(merged_data, title_id):
    distribution_data = _filter_by_title_id(merged_data, title_id)
    distribution_data = distribution_data.groupby("score").size().reset_index(name="count")
    total_submissions = distribution_data["count"].sum()
    if total_submissions == 0:
        distribution_data["percentage"] = 0.0
    else:
        distribution_data["percentage"] = distribution_data["count"] / total_submissions * 100
    return distribution_data.to_dict(orient="records")


def get_avg_score(merged_data, title_id):
    avg_score = _filter_by_title_id(merged_data, title_id)["score"].mean()
    return float(avg_score) if pd.notna(avg_score) else 0.0


def get_sum_submit(merged_data, title_id):
    sum_submit = _filter_by_title_id(merged_data, title_id)["title_ID"].count()
    return float(sum_submit)


def get_titles_data_by_knowledge(merged_data, knowledge, limit=None):
    titles = merged_data[merged_data["knowledge"] == knowledge][["title_ID", "knowledge"]].drop_duplicates()
    if limit is not None:
        titles = titles.head(limit)
    return [_build_title_payload(merged_data, row) for _, row in titles.iterrows()]


def get_all_titles_data(merged_data, limit=None):
    titles = merged_data[["title_ID", "knowledge"]].drop_duplicates()
    if limit is not None:
        titles = titles.head(limit)
    return [_build_title_payload(merged_data, row) for _, row in titles.iterrows()]
