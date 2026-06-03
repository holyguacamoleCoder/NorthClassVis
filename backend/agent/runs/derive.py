"""Plan how to derive a new run from a parent run + patch."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import ToolRun

QUERY_PARAM_KEYS = frozenset({
    "resource",
    "select",
    "where",
    "filter",
    "group_by",
    "order_by",
    "limit",
    "class",
    "classes",
    "majors",
    "week_range",
    "student_ids",
})

AGG_PARAM_KEYS = frozenset({
    "metrics",
    "dimensions",
    "bind",
    "input",
})


@dataclass
class DerivePlan:
    strategy: str  # requery | reaggregate | reuse_aggregate
    merged_params: dict[str, Any]
    parent_run_id: str
    patch: dict[str, Any] = field(default_factory=dict)
    reuse_result_ref: str | None = None
    reuse_dataset_id: str | None = None


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in patch.items():
        if (
            key in out
            and isinstance(out[key], dict)
            and isinstance(value, dict)
        ):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _patch_touches_query(patch: dict[str, Any]) -> bool:
    if QUERY_PARAM_KEYS.intersection(patch.keys()):
        return True
    where = patch.get("where")
    return isinstance(where, dict) and bool(where)


def _patch_touches_aggregate(patch: dict[str, Any]) -> bool:
    return bool(AGG_PARAM_KEYS.intersection(patch.keys()))


def normalize_patch_for_parent(parent: ToolRun, patch: dict[str, Any]) -> dict[str, Any]:
    """Map grouping intent to dimensions when parent already has row-level query cache."""
    clean = {k: v for k, v in patch.items() if v is not None}
    if "group_by" not in clean:
        return clean

    group_val = clean["group_by"]
    parent_gb = parent.params.get("group_by") if isinstance(parent.params, dict) else None

    if parent.tool_name == "aggregate_data":
        clean.pop("group_by", None)
        clean.setdefault("dimensions", group_val)
        return clean

    if parent.tool_name == "query_data":
        if parent_gb:
            return clean
        if parent.result_ref or parent.dataset_id:
            clean.pop("group_by", None)
            clean.setdefault("dimensions", group_val)
    return clean


def resolve_reaggregate_source(
    parent: ToolRun,
    registry: Any | None = None,
) -> tuple[str | None, str | None]:
    """Return (result_ref, dataset_id) for aggregate on cached query rows."""
    if parent.tool_name == "query_data":
        return parent.result_ref, parent.dataset_id

    inp = parent.params.get("input") if isinstance(parent.params.get("input"), dict) else {}
    ref = inp.get("result_ref")
    ds = inp.get("dataset_id") or parent.dataset_id
    if ref or ds:
        return (str(ref) if ref else None, str(ds) if ds else None)

    if parent.parent_run_id and registry is not None:
        ancestor = registry.get_run(parent.parent_run_id)
        if ancestor is not None:
            return resolve_reaggregate_source(ancestor, registry)

    return parent.result_ref, parent.dataset_id


def plan_derive(
    parent: ToolRun,
    patch: dict[str, Any],
    *,
    registry: Any | None = None,
) -> DerivePlan:
    """Decide whether to re-query or re-aggregate on cached result_ref."""
    clean_patch = normalize_patch_for_parent(parent, patch)
    merged = _deep_merge(dict(parent.params or {}), clean_patch)

    if parent.tool_name == "aggregate_data":
        if _patch_touches_query(clean_patch):
            strategy = "requery"
            reuse_ref, reuse_ds = None, None
        else:
            reuse_ref, reuse_ds = resolve_reaggregate_source(parent, registry)
            strategy = "reaggregate"
            if _patch_touches_aggregate(clean_patch):
                strategy = "reuse_aggregate" if not clean_patch else "reaggregate"
        return DerivePlan(
            strategy=strategy,
            merged_params=merged,
            parent_run_id=parent.run_id,
            patch=clean_patch,
            reuse_result_ref=reuse_ref,
            reuse_dataset_id=reuse_ds,
        )

    # parent is query_data (or other)
    if _patch_touches_aggregate(clean_patch) and not _patch_touches_query(clean_patch):
        reuse_ref, reuse_ds = resolve_reaggregate_source(parent, registry)
        return DerivePlan(
            strategy="reaggregate",
            merged_params=merged,
            parent_run_id=parent.run_id,
            patch=clean_patch,
            reuse_result_ref=reuse_ref,
            reuse_dataset_id=reuse_ds,
        )

    return DerivePlan(
        strategy="requery",
        merged_params=merged,
        parent_run_id=parent.run_id,
        patch=clean_patch,
        reuse_result_ref=None,
        reuse_dataset_id=None,
    )
