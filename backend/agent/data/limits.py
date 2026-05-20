from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class QueryLimits:
    max_rows: int = 5000
    max_bytes: int = 1_048_576
    timeout_sec: int = 60
    column_whitelist: list[str] | None = None

    @classmethod
    def from_registry_defaults(cls, registry_defaults: dict | None) -> "QueryLimits":
        limits = (registry_defaults or {}).get("limits") or {}
        return cls(
            max_rows=int(limits.get("max_rows", 5000)),
            max_bytes=int(limits.get("max_bytes", 1_048_576)),
            timeout_sec=int(limits.get("timeout_sec", 60)),
        )


def apply_column_whitelist(df: pd.DataFrame, whitelist: list[str] | None) -> pd.DataFrame:
    if not whitelist:
        return df
    missing = [c for c in whitelist if c not in df.columns]
    if missing:
        raise ValueError(f"列白名单中不存在于 DataFrame: {missing}")
    return df[list(whitelist)]


def apply_row_limit(
    df: pd.DataFrame,
    limits: QueryLimits,
) -> tuple[pd.DataFrame, bool, int]:
    """返回 (受限 df, truncated, rows_scanned)。"""
    scanned = len(df)
    if scanned <= limits.max_rows:
        return df, False, scanned
    return df.iloc[: limits.max_rows].copy(), True, scanned
