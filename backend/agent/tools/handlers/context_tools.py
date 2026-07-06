from __future__ import annotations

import json
from typing import Any

from data.filter_context import FilterContext, merge_defaults
from data.visual_links import (
    enrich_week_view_student_ids,
    enrich_week_view_week_range,
    validate_links,
    warn_week_view_missing_student_ids,
)


def _json_result(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def run_get_current_filter_context(
    include_student_ids: bool = False,
    **kwargs: Any,
) -> str:
    raw = kwargs.pop("_filter_context", None)
    if isinstance(raw, FilterContext):
        ctx = raw
    elif isinstance(raw, dict):
        ctx = FilterContext.from_dict(raw)
    else:
        ctx = None
    ctx = merge_defaults(ctx)
    if include_student_ids:
        return _json_result(ctx.to_dict())
    return _json_result(ctx.to_summary_dict())


def run_build_visual_links(
    links: list[dict] | None = None,
    archetype: str | None = None,
    **kwargs: Any,
) -> str:
    raw_fc = kwargs.pop("_filter_context", None)
    fc: FilterContext | None
    if isinstance(raw_fc, FilterContext):
        fc = merge_defaults(raw_fc)
    elif isinstance(raw_fc, dict):
        fc = merge_defaults(FilterContext.from_dict(raw_fc))
    else:
        fc = None
    payload = validate_links(links, archetype=archetype)
    payload["visual_links"] = enrich_week_view_week_range(
        payload.get("visual_links") or [],
        fc,
    )
    payload["visual_links"], student_notes = enrich_week_view_student_ids(
        payload.get("visual_links") or [],
        fc,
    )
    payload["warnings"] = list(payload.get("warnings") or []) + student_notes + warn_week_view_missing_student_ids(
        payload.get("visual_links") or [],
        fc,
    )
    if fc is not None and not payload.get("typical_student_ids"):
        from data.filter_context import sample_typical_student_ids

        typical = sample_typical_student_ids(
            fc.classes or (),
            majors=fc.majors,
            week_range=fc.week_range,
            limit=3,
        )
        if typical:
            payload["typical_student_ids"] = typical
    return _json_result(payload)
