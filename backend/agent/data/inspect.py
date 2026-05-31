from __future__ import annotations

from typing import Any

import pandas as pd

from .registry import resolve
from .column_aliases import RESOURCE_COLUMNS
from .tabular import _cell_value, _infer_column_type


def inspect_resource(
    resource: str,
    *,
    resolve_params: dict[str, Any] | None = None,
    data_dir=None,
    sample_size: int = 5,
) -> dict:
    """返回 resource 的列、样例行与行数估计。"""
    resolved = resolve(resource, data_dir=data_dir, **(resolve_params or {}))
    df = resolved.load()
    if not isinstance(df, pd.DataFrame):
        raise TypeError("loader 未返回 DataFrame")

    columns = []
    for col in df.columns:
        entry: dict[str, Any] = {
            "name": str(col),
            "type": _infer_column_type(df[col].dtype),
        }
        columns.append(entry)

    sample_df = df.head(sample_size)
    sample_rows = [
        [_cell_value(sample_df.iloc[i][col]) for col in sample_df.columns]
        for i in range(len(sample_df))
    ]

    return {
        "resource": resource,
        "columns": columns,
        "sample_rows": sample_rows,
        "row_count_estimate": len(df),
        "column_hint": list(RESOURCE_COLUMNS.get(resource, ())),
    }
