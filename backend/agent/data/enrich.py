"""Generic left-join enrich: attach lookup resource columns onto a prior result.

Mid-term path for multi-resource analysis without baking every join into loaders.
Always left-join; lookup keys are de-duplicated to avoid row explosion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .exceptions import InvalidParameterError
from .limits import QueryLimits
from .query import PREVIEW_ROW_LIMIT, _build_tabular_from_df
from .registry import default_limits, resolve
from .result_store import load_result
from .tabular import dataframe_to_tabular  # noqa: F401 — kept for clarity
from .aggregate import _tabular_to_dataframe


@dataclass
class EnrichSpec:
    input: dict[str, Any]
    lookup: str
    on: str | dict[str, str] | list[Any]
    columns: list[str] | None = None
    rename: dict[str, str] | None = None
    resolve_params: dict[str, Any] = field(default_factory=dict)
    compute_score_rate: bool = False


def _parse_join_keys(
    on: str | dict[str, str] | list[Any],
) -> list[tuple[str, str]]:
    """Return list of (left_col, right_col)."""
    if isinstance(on, str):
        key = on.strip()
        if not key:
            raise InvalidParameterError("on 不能为空", param="on")
        return [(key, key)]
    if isinstance(on, dict):
        if not on:
            raise InvalidParameterError("on 映射不能为空", param="on")
        return [(str(left), str(right)) for left, right in on.items()]
    if isinstance(on, list):
        pairs: list[tuple[str, str]] = []
        for item in on:
            if isinstance(item, str):
                pairs.append((item, item))
            elif isinstance(item, dict) and len(item) == 1:
                left, right = next(iter(item.items()))
                pairs.append((str(left), str(right)))
            else:
                raise InvalidParameterError(
                    "on 列表项须为字符串或单键对象 {left: right}",
                    param="on",
                )
        if not pairs:
            raise InvalidParameterError("on 列表不能为空", param="on")
        return pairs
    raise InvalidParameterError("on 须为字符串、映射或列表", param="on")


def _load_enrich_left(inp: dict[str, Any]) -> tuple[pd.DataFrame, str]:
    if not inp:
        raise InvalidParameterError(
            "enrich_data 需要 input（result_ref 或 inline rows+schema）",
            param="input",
        )
    if "result_ref" in inp:
        payload = load_result(str(inp["result_ref"]))
        return _tabular_to_dataframe(payload)
    if "rows" in inp and "schema" in inp:
        payload = {
            "schema": inp["schema"],
            "rows": inp["rows"],
            "meta": {"resource": "inline"},
        }
        return _tabular_to_dataframe(payload)
    raise InvalidParameterError(
        "input 须包含 result_ref 或 inline rows+schema（dataset_id 由运行时解析为 result_ref）",
        param="input",
    )


def execute_enrich(
    spec: EnrichSpec,
    *,
    limits: QueryLimits | None = None,
    preview_limit: int = PREVIEW_ROW_LIMIT,
    data_dir=None,
) -> dict:
    limits = limits or default_limits()
    left_df, left_resource = _load_enrich_left(spec.input)

    pairs = _parse_join_keys(spec.on)
    left_keys = [p[0] for p in pairs]
    right_keys = [p[1] for p in pairs]

    missing_left = [k for k in left_keys if k not in left_df.columns]
    if missing_left:
        raise InvalidParameterError(
            f"左表缺少 join 键: {missing_left}；可用列: {list(left_df.columns)[:30]}",
            param="on",
        )

    resolved = resolve(spec.lookup, data_dir=data_dir, **(spec.resolve_params or {}))
    right_df = resolved.load()
    if not isinstance(right_df, pd.DataFrame):
        raise InvalidParameterError("lookup loader 未返回 DataFrame", param="lookup")

    missing_right = [k for k in right_keys if k not in right_df.columns]
    if missing_right:
        raise InvalidParameterError(
            f"lookup={spec.lookup!r} 缺少 join 键: {missing_right}；"
            f"可用列: {list(right_df.columns)[:30]}",
            param="on",
        )

    rename = dict(spec.rename or {})
    # Avoid colliding with left.score when attaching title_info.score
    if (
        spec.lookup == "title_info"
        and "score" in left_df.columns
        and "score" not in rename
    ):
        want_score = not spec.columns or "score" in spec.columns or "full_score" in (
            rename.values() if rename else []
        )
        if want_score and (not spec.columns or "score" in spec.columns):
            rename.setdefault("score", "full_score")

    if spec.columns:
        bring = list(spec.columns)
    else:
        bring = [c for c in right_df.columns if c not in right_keys]

    select_right = list(dict.fromkeys([*right_keys, *bring]))
    unknown = [c for c in select_right if c not in right_df.columns]
    if unknown:
        raise InvalidParameterError(
            f"lookup 列不存在: {unknown}；可用: {list(right_df.columns)[:30]}",
            param="columns",
        )

    right_part = right_df[select_right].copy()
    before = len(right_part)
    right_part = right_part.drop_duplicates(subset=right_keys, keep="first")
    deduped = before - len(right_part)

    for src, dst in list(rename.items()):
        if src in right_part.columns and src not in right_keys:
            right_part = right_part.rename(columns={src: dst})

    # Align right key names to left for merge
    key_rename: dict[str, str] = {}
    for left_k, right_k in pairs:
        if right_k != left_k and right_k in right_part.columns:
            key_rename[right_k] = left_k
    if key_rename:
        right_part = right_part.rename(columns=key_rename)

    overlap = [
        c for c in right_part.columns if c in left_df.columns and c not in left_keys
    ]
    if overlap:
        right_part = right_part.drop(columns=overlap)

    merged = left_df.merge(right_part, on=left_keys, how="left")

    if spec.compute_score_rate or (
        "score" in merged.columns
        and "full_score" in merged.columns
        and "score_rate" not in merged.columns
    ):
        earned = pd.to_numeric(merged["score"], errors="coerce")
        full = pd.to_numeric(merged["full_score"], errors="coerce")
        rate = earned / full
        merged["score_rate"] = rate.where(full.notna() & (full > 0))

    out_resource = f"{left_resource}+{spec.lookup}"
    result = _build_tabular_from_df(
        merged,
        out_resource,
        rows_scanned=len(merged),
        limits=limits,
        preview_limit=preview_limit,
    )
    meta = result.setdefault("meta", {})
    meta["enrich"] = {
        "lookup": spec.lookup,
        "on": [{"left": a, "right": b} for a, b in pairs],
        "columns_added": [c for c in merged.columns if c not in left_df.columns],
        "lookup_rows_deduped": int(deduped),
        "how": "left",
    }
    meta["grain"] = "row"
    meta.setdefault(
        "metric_hint",
        "enrich 已左连接 lookup 列；继续用本结果 dataset_id 做 aggregate_data。"
        "正确率：sum(score)/sum(full_score) 或 mean(score_rate)。",
    )
    return result
