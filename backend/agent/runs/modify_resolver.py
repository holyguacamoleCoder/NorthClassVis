"""Detect natural-language modify intent and extract param patches."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .models import DATA_RUN_TOOLS, TERMINAL_RUN_STATUSES, RunStatus, ToolRun

MODIFY_MARKERS = (
    "改成",
    "改为",
    "换成",
    "不对",
    "不要",
    "别按",
    "重新",
    "改一下",
    "修正",
    "加上",
    "去掉",
    "排除",
    "剔除",
    "改为按",
    "改成按",
)

GROUP_BY_PATTERNS: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(r"按周|按周次|每周|周汇总"), ["week"]),
    (re.compile(r"按月|每月|月汇总|月份"), ["month"]),
    (re.compile(r"按季度|每季度|季度汇总"), ["quarter"]),
    (re.compile(r"按专业|分专业"), ["major"]),
    (re.compile(r"按班级|分班"), ["class"]),
]


@dataclass
class ModifyHint:
    parent_run_id: str
    patch: dict[str, Any] = field(default_factory=dict)
    strategy: str | None = None
    parent_tool: str | None = None
    source: str = "auto"  # auto | explicit


def looks_like_modify(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    if any(marker in text for marker in MODIFY_MARKERS):
        return True
    for pattern, _ in GROUP_BY_PATTERNS:
        if pattern.search(text) and len(text) < 120:
            return True
    return False


def _should_map_group_to_dimensions(
    parent_params: dict[str, Any],
    parent_tool: str | None,
) -> bool:
    if parent_tool == "aggregate_data":
        return True
    if parent_tool != "query_data":
        return False
    parent_gb = parent_params.get("group_by")
    return not parent_gb


def extract_patch_from_message(
    message: str,
    parent_params: dict[str, Any] | None = None,
    *,
    parent_tool: str | None = None,
) -> dict[str, Any]:
    """Rule-based patch extraction from teacher message."""
    text = (message or "").strip()
    patch: dict[str, Any] = {}
    parent_params = parent_params or {}

    for pattern, group_val in GROUP_BY_PATTERNS:
        if pattern.search(text):
            if _should_map_group_to_dimensions(parent_params, parent_tool):
                patch["dimensions"] = group_val
            else:
                patch["group_by"] = group_val
            break

    if re.search(r"全量|不要\s*limit|去掉\s*限制|不限行", text):
        patch["limit"] = None

    class_match = re.search(r"Class\s*\d+", text, re.IGNORECASE)
    if class_match:
        patch["class"] = class_match.group(0).replace(" ", "")

    if "退货" in text and "剔除" in text:
        where = dict(parent_params.get("where") or {})
        where["exclude_returns"] = True
        patch["where"] = where

    if re.search(r"及格率", text):
        patch.setdefault(
            "metrics",
            [{"op": "mean", "field": "score", "as": "pass_rate"}],
        )

    return patch


def pick_parent_run(runs: list[ToolRun], *, prefer_executing: bool = True) -> ToolRun | None:
    if not runs:
        return None
    data_runs = [r for r in runs if r.tool_name in DATA_RUN_TOOLS]
    if not data_runs:
        return None

    if prefer_executing:
        for run in reversed(data_runs):
            if run.status in (RunStatus.EXECUTING, RunStatus.CANCELLING, RunStatus.QUEUED):
                if run.superseded_by:
                    continue
                return run

    for run in reversed(data_runs):
        if run.status in TERMINAL_RUN_STATUSES and run.status != RunStatus.SUPERSEDED:
            if run.superseded_by:
                continue
            return run
        if run.status == RunStatus.COMPLETED and not run.superseded_by:
            return run
    return data_runs[-1]


def resolve_modify_intent(
    message: str,
    runs: list[ToolRun],
    *,
    explicit_parent_run_id: str | None = None,
    explicit_patch: dict[str, Any] | None = None,
) -> ModifyHint | None:
    if explicit_parent_run_id:
        parent = next((r for r in runs if r.run_id == explicit_parent_run_id), None)
        if parent is None:
            return None
        patch = dict(explicit_patch or {})
        if not patch and message:
            patch = extract_patch_from_message(
                message,
                parent.params,
                parent_tool=parent.tool_name,
            )
        return ModifyHint(
            parent_run_id=parent.run_id,
            patch=patch,
            parent_tool=parent.tool_name,
            source="explicit",
        )

    if not looks_like_modify(message):
        return None

    parent = pick_parent_run(runs)
    if parent is None:
        return None

    patch = extract_patch_from_message(
        message,
        parent.params,
        parent_tool=parent.tool_name,
    )
    if not patch and not looks_like_modify(message):
        return None

    return ModifyHint(
        parent_run_id=parent.run_id,
        patch=patch,
        parent_tool=parent.tool_name,
        source="auto",
    )
