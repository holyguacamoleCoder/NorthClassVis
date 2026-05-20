from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from core import data_loader

from .exceptions import InvalidParameterError, ResourceLoadError

_CLASS_NAME_RE = re.compile(r"^Class\d+$", re.IGNORECASE)


def project_data_dir(data_dir: Path | None = None) -> Path:
    if data_dir is not None:
        return Path(data_dir)
    return data_loader.DATA_DIR


def validate_class_name(class_name: str) -> None:
    if not class_name or not isinstance(class_name, str):
        raise InvalidParameterError("class 必须为非空字符串", param="class")
    if not _CLASS_NAME_RE.match(class_name.strip()):
        raise InvalidParameterError(
            f"非法班级名: {class_name!r}（期望形如 Class1）",
            param="class",
        )


def validate_classes(classes: list[str], data_dir: Path | None = None) -> list[str]:
    if not classes:
        raise InvalidParameterError("classes 不能为空", param="classes")
    root = project_data_dir(data_dir)
    submissions_dir = root / "Data_SubmitRecord"
    normalized: list[str] = []
    for raw in classes:
        name = raw.strip() if isinstance(raw, str) else ""
        validate_class_name(name)
        path = submissions_dir / f"SubmitRecord-{name}.csv"
        if not path.is_file():
            raise InvalidParameterError(
                f"班级数据文件不存在: {path}",
                param="class",
            )
        normalized.append(name)
    return normalized


def repo_root(data_dir: Path | None = None) -> Path:
    return project_data_dir(data_dir).parent


def resolve_csv_path(path_pattern: str, data_dir: Path | None, **params) -> Path:
    formatted = path_pattern.format(**params)
    path = Path(formatted)
    if not path.is_absolute():
        path = repo_root(data_dir) / path
    if not path.is_file():
        raise ResourceLoadError(f"数据文件不存在: {path}")
    return path


def load_csv_resource(path_pattern: str, data_dir: Path | None = None, **params) -> pd.DataFrame:
    path = resolve_csv_path(path_pattern, data_dir, **params)
    df = data_loader.load_data(path)
    if df is None:
        raise ResourceLoadError(f"无法加载 CSV: {path}")
    return df


def load_student_info(data_dir: Path | None = None) -> pd.DataFrame:
    return load_csv_resource("data/Data_StudentInfo.csv", data_dir)


def load_title_info(data_dir: Path | None = None) -> pd.DataFrame:
    return load_csv_resource("data/Data_TitleInfo.csv", data_dir)


def load_submit_record(class_name: str, data_dir: Path | None = None) -> pd.DataFrame:
    validate_class_name(class_name)
    validate_classes([class_name], data_dir)
    return data_loader.load_submissions_by_classes(
        project_data_dir(data_dir) / "Data_SubmitRecord",
        [class_name],
    )


def load_submit_records(classes: list[str], data_dir: Path | None = None) -> pd.DataFrame:
    validated = validate_classes(classes, data_dir)
    return data_loader.load_submissions_by_classes(
        project_data_dir(data_dir) / "Data_SubmitRecord",
        validated,
    )
