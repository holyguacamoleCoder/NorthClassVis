from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
SUBMISSIONS_DIR = DATA_DIR / "Data_SubmitRecord"
SUBMISSIONS_FILE_PATH = SUBMISSIONS_DIR / "SubmitRecord-Class1.csv"
TITLE_INFO_PATH = DATA_DIR / "Data_TitleInfo.csv"
STUDENT_INFO_PATH = DATA_DIR / "Data_StudentInfo.csv"

# Backward-compatible aliases for legacy callers.
class_dir = SUBMISSIONS_DIR
classFilename = SUBMISSIONS_FILE_PATH
titleFilename = TITLE_INFO_PATH
studentFilename = STUDENT_INFO_PATH


def load_data(filename):
    try:
        return pd.read_csv(filename)
    except Exception as exc:
        print(f"Error loading data: {exc}")
        return None


def _normalize_class_name(class_item):
    if isinstance(class_item, dict):
        if not class_item.get("checked", True):
            return None
        return class_item.get("text")
    return class_item


def load_submissions_by_classes(submissions_dir, class_list):
    normalized_classes = [
        class_name
        for class_name in (_normalize_class_name(item) for item in class_list)
        if class_name
    ]
    if not normalized_classes:
        return pd.DataFrame()
    return pd.concat(
        (
            load_data(Path(submissions_dir) / f"SubmitRecord-{class_name}.csv")
            for class_name in normalized_classes
        ),
        axis=0,
        ignore_index=True,
    )


def merge_dataframes_or_files(
    left_df=None,
    right_df=None,
    left_path=None,
    right_path=None,
    on=None,
    left_columns=None,
    right_columns=None,
):
    merged_left = left_df if left_df is not None else load_data(left_path)
    merged_right = right_df if right_df is not None else load_data(right_path)
    merged_left = merged_left[left_columns] if left_columns is not None else merged_left
    merged_right = merged_right[right_columns] if right_columns is not None else merged_right
    return pd.merge(merged_left, merged_right, on=on, how="left")


def process_non_numeric_values(df):
    """将 timeconsume/memory 转为数值并用组内均值填充 NaN。不修改入参，返回新 DataFrame。"""
    processed_df = df.copy()
    processed_df["timeconsume"] = pd.to_numeric(processed_df["timeconsume"], errors="coerce")
    processed_df["memory"] = pd.to_numeric(processed_df["memory"], errors="coerce")
    processed_df["timeconsume"] = processed_df.groupby(
        ["student_ID", "knowledge"]
    )["timeconsume"].transform(lambda series: series.fillna(series.mean()))
    processed_df["memory"] = processed_df.groupby(["student_ID", "knowledge"])[
        "memory"
    ].transform(lambda series: series.fillna(series.mean()))
    return processed_df


def contact_df(classDir, classList):
    return load_submissions_by_classes(classDir, classList)


def contact_data(classDir, classList):
    return load_submissions_by_classes(classDir, classList)


def merge_df_or_file(
    df1=None,
    df2=None,
    filename1=None,
    filename2=None,
    on=None,
    filter_col1=None,
    filter_col2=None,
):
    return merge_dataframes_or_files(
        left_df=df1,
        right_df=df2,
        left_path=filename1,
        right_path=filename2,
        on=on,
        left_columns=filter_col1,
        right_columns=filter_col2,
    )


def merge_data(filename1, filename2, on="title_ID"):
    return merge_dataframes_or_files(left_path=filename1, right_path=filename2, on=on)
