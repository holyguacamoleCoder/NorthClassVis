"""Apply derive / modify context to tool dispatch parameters."""

from __future__ import annotations

from typing import Any

from .derive import DerivePlan
from .registry import RunRegistry


def merge_tool_params(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in overlay.items():
        if key.startswith("_"):
            continue
        if (
            key in out
            and isinstance(out[key], dict)
            and isinstance(value, dict)
        ):
            out[key] = {**out[key], **value}
        else:
            out[key] = value
    return out


def apply_derive_plan_to_params(
    tool_name: str,
    params: dict[str, Any],
    plan: DerivePlan,
    *,
    parent_run: Any | None = None,
) -> dict[str, Any]:
    merged = merge_tool_params(plan.merged_params, params)

    if tool_name == "query_data" and plan.strategy == "reaggregate" and plan.reuse_result_ref:
        # Caller should use aggregate_data; keep query params for reference only.
        merged.setdefault("_reuse_result_ref", plan.reuse_result_ref)

    if tool_name == "aggregate_data" and plan.strategy in ("reaggregate", "reuse_aggregate"):
        inp = dict(merged.get("input") or {})
        if plan.reuse_result_ref:
            inp.setdefault("result_ref", plan.reuse_result_ref)
        dataset_id = plan.reuse_dataset_id
        if not dataset_id and parent_run is not None:
            dataset_id = getattr(parent_run, "dataset_id", None)
            parent_inp = (parent_run.params or {}).get("input") if parent_run else None
            if isinstance(parent_inp, dict) and parent_inp.get("dataset_id"):
                dataset_id = str(parent_inp["dataset_id"])
        if dataset_id:
            inp.setdefault("dataset_id", dataset_id)
        merged["input"] = inp

    merged["_derive_from_run_id"] = plan.parent_run_id
    merged["_derive_strategy"] = plan.strategy
    merged["_derive_patch"] = dict(plan.patch)
    return merged


import re

_RUN_MODIFY_BLOCK_RE = re.compile(
    r"\[run_modify\].*?\[/run_modify\]\s*",
    re.DOTALL,
)
_RUN_MODIFY_INSTRUCTION_RE = re.compile(
    r"^这是对上一轮数据计算的修改：.*?(?:\n\n|\Z)",
    re.DOTALL,
)


def strip_run_modify_from_user_content(content: str) -> str:
    """Remove internal run_modify protocol from persisted / displayed user text."""
    text = str(content or "")
    text = _RUN_MODIFY_BLOCK_RE.sub("", text)
    text = _RUN_MODIFY_INSTRUCTION_RE.sub("", text)
    return text.strip()


def build_modify_user_block(
    *,
    parent_run_id: str,
    parent_tool: str,
    parent_params: dict[str, Any],
    patch: dict[str, Any],
    strategy: str | None,
) -> str:
    import json

    payload = {
        "parent_run_id": parent_run_id,
        "parent_tool": parent_tool,
        "patch": patch,
        "strategy": strategy,
        "parent_params_preview": {
            k: parent_params.get(k)
            for k in ("resource", "class", "classes", "group_by", "where", "limit")
            if parent_params.get(k) is not None
        },
    }
    return (
        "[run_modify]\n"
        + json.dumps(payload, ensure_ascii=False, default=str)
        + "\n[/run_modify]\n"
        "这是对上一轮数据计算的修改：请继承 parent 未改条件，仅应用 patch；"
        "优先使用 derive_from_run_id / 合并参数，避免不必要的全量重查。"
    )


def extract_run_meta_from_result(content: str) -> tuple[str | None, str | None]:
    """Parse result_ref / dataset_id from tool JSON result."""
    import json

    text = (content or "").strip()
    if not text.startswith("{"):
        return None, None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None, None
    meta = payload.get("meta") if isinstance(payload, dict) else None
    if not isinstance(meta, dict):
        return None, None
    ref = meta.get("result_ref")
    dataset_id = meta.get("dataset_id")
    return (
        str(ref) if ref else None,
        str(dataset_id) if dataset_id else None,
    )
