from __future__ import annotations

import json
from typing import Any

from data.filter_context import FilterContext, merge_defaults
from data.visual_links import validate_links


def _json_result(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def run_get_current_filter_context(**kwargs: Any) -> str:
    raw = kwargs.pop("_filter_context", None)
    if isinstance(raw, FilterContext):
        ctx = raw
    elif isinstance(raw, dict):
        ctx = FilterContext.from_dict(raw)
    else:
        ctx = None
    ctx = merge_defaults(ctx)
    return _json_result(ctx.to_dict())


def run_build_visual_links(
    links: list[dict] | None = None,
    archetype: str | None = None,
    **kwargs: Any,
) -> str:
    payload = validate_links(links, archetype=archetype)
    return _json_result(payload)
