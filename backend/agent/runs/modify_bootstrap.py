"""Auto-run the first data tool on modify / derive turns."""

from __future__ import annotations

import json
import uuid
from typing import Any

from .apply import apply_derive_plan_to_params


def _public_params(raw: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in raw.items() if not str(k).startswith("_")}


def build_modify_bootstrap_call(
    modify_context: dict[str, Any],
    *,
    run_registry: Any,
) -> tuple[list[dict[str, Any]], str] | None:
    """
    Build a single synthetic tool call for modify bootstrap.
    Returns (tool_calls, hint_text) or None.
    """
    if not modify_context or modify_context.get("_bootstrapped"):
        return None

    strategy = modify_context.get("strategy")
    parent_run_id = modify_context.get("parent_run_id")
    if not parent_run_id or not run_registry:
        return None

    tool_name: str | None = None
    if strategy in ("reaggregate", "reuse_aggregate"):
        tool_name = "aggregate_data"
    elif strategy == "requery":
        tool_name = "query_data"
    if not tool_name:
        return None

    patch = dict(modify_context.get("patch") or {})
    plan = run_registry.derive_run(str(parent_run_id), patch)
    if plan is None:
        return None

    parent_run = run_registry.get_run(str(parent_run_id))
    parent_params = dict(modify_context.get("parent_params") or {})
    base: dict[str, Any] = {}

    if tool_name == "aggregate_data":
        for key in ("metrics", "dimensions", "input", "bind", "window"):
            if key in parent_params and parent_params[key] is not None:
                base[key] = parent_params[key]
        for key in ("metrics", "dimensions", "bind", "window"):
            if key in patch and patch[key] is not None:
                base[key] = patch[key]
        if not base.get("metrics"):
            base["metrics"] = [{"op": "count", "as": "n"}]
    else:
        skip = frozenset({"metrics", "dimensions", "input", "bind", "window"})
        for key, value in (plan.merged_params or {}).items():
            if key in skip or str(key).startswith("_"):
                continue
            if value is not None:
                base[key] = value

    merged = apply_derive_plan_to_params(
        tool_name,
        base,
        plan,
        parent_run=parent_run,
    )
    public_args = _public_params(merged)
    call_id = f"call_modify_{uuid.uuid4().hex[:12]}"
    tool_calls = [{
        "id": call_id,
        "name": tool_name,
        "arguments": json.dumps(public_args, ensure_ascii=False, default=str),
    }]
    hint = (
        f"正在应用数据修改（{tool_name}，strategy={strategy}）…"
    )
    modify_context["_bootstrapped"] = True
    return tool_calls, hint
