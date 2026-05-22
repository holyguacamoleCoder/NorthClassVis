from __future__ import annotations

import json
from typing import Any

from data.aggregate import AggregateSpec, execute_aggregate
from data.exceptions import DataResourceError, InvalidParameterError
from data.inspect import inspect_resource
from data.param_validation import normalize_query_resource, validate_resolve_params
from data.query import QuerySpec, execute_query

_RESOLVE_KEYS = frozenset({"class", "classes", "majors", "week_range", "student_ids"})

# Substring matched by loop_guards when aggregate_data fails without input.
AGGREGATE_INPUT_REQUIRED_MARKER = "aggregate_data 需要 input"


def _resolve_params(kwargs: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in kwargs.items() if k in _RESOLVE_KEYS and v is not None}


def _json_result(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _enrich_query_payload(payload: dict, notes: list[str] | None = None) -> dict:
    meta = payload.setdefault("meta", {})
    ref = meta.get("result_ref")
    if ref:
        meta["next_step"] = {
            "tool": "aggregate_data",
            "example": {
                "input": {"result_ref": ref},
                "metrics": [
                    {"op": "count", "field": "score", "as": "count"},
                    {"op": "mean", "field": "score", "as": "avg_score"},
                ],
            },
        }
    if notes:
        meta["normalization_notes"] = notes
    return payload


def _aggregate_input_required_message(
    *,
    last_result_ref: str | None = None,
) -> str:
    hint = (
        "Error: aggregate_data 需要 input（含 result_ref 或 inline schema+rows）。"
        "请先调用 query_data，再使用返回的 meta.result_ref，例如："
        ' input={"result_ref": "<uuid>.json"}, metrics=[{"op":"count","field":"score","as":"n"}]'
    )
    if last_result_ref:
        hint += f'。本会话最近一次 query 的 result_ref: "{last_result_ref}"（可填入 input）。'
    return hint


def run_inspect_schema(resource: str | None = None, **kwargs: Any) -> str:
    if not resource:
        return "Error: resource is required"
    try:
        resource, kwargs, notes = normalize_query_resource(resource, kwargs)
        resolve = _resolve_params(kwargs)
        validate_resolve_params(resource, resolve)
        payload = inspect_resource(
            resource,
            resolve_params=resolve,
            data_dir=kwargs.get("data_dir"),
        )
        if notes:
            payload["normalization_notes"] = notes
        return _json_result(payload)
    except DataResourceError as exc:
        return f"Error: {exc}"
    except Exception as exc:
        return f"Error: inspect_schema failed: {exc}"


def run_query_data(
    resource: str | None = None,
    select: list[str] | None = None,
    where: dict | None = None,
    filter: dict | None = None,
    group_by: list[str] | None = None,
    order_by: list[dict] | None = None,
    limit: int | None = None,
    **kwargs: Any,
) -> str:
    if not resource:
        return "Error: resource is required"
    if where is None and filter is not None:
        where = filter
    try:
        resource, kwargs, notes = normalize_query_resource(resource, kwargs)
        resolve = _resolve_params(kwargs)
        validate_resolve_params(resource, resolve)
        spec = QuerySpec(
            resource=resource,
            select=select,
            where=where,
            group_by=group_by,
            order_by=order_by,
            limit=limit,
            resolve_params=resolve,
        )
        result = execute_query(spec, data_dir=kwargs.get("data_dir"))
        result["resource"] = resource
        _enrich_query_payload(result, notes)
        return _json_result(result)
    except DataResourceError as exc:
        return f"Error: {exc}"
    except Exception as exc:
        return f"Error: query_data failed: {exc}"


def _composite_query_for_aggregate(
    resource: str,
    metrics: list[dict],
    kwargs: dict[str, Any],
) -> dict | None:
    """When aggregate omits input but passes resource + filters, run query first."""
    resolve = _resolve_params(kwargs)
    if resource == "submit_record" and not resolve.get("class") and not resolve.get("classes"):
        return None
    if resource == "submit_record_joined" and not resolve.get("classes"):
        return None
    fields = {m.get("field") for m in metrics if m.get("field")}
    select = [f for f in fields if f] or None
    raw = run_query_data(
        resource=resource,
        select=select,
        limit=kwargs.get("limit"),
        data_dir=kwargs.get("data_dir"),
        **{k: v for k, v in kwargs.items() if k in _RESOLVE_KEYS or k == "class"},
    )
    if raw.startswith("Error:"):
        return None
    return json.loads(raw)


def run_aggregate_data(
    input: dict | None = None,
    metrics: list[dict] | None = None,
    dimensions: list[str] | None = None,
    window: dict | None = None,
    resource: str | None = None,
    **kwargs: Any,
) -> str:
    last_result_ref = kwargs.pop("_last_result_ref", None)

    if not input and last_result_ref:
        input = {"result_ref": last_result_ref}

    if not input and resource and metrics:
        resource, kwargs, _notes = normalize_query_resource(resource, kwargs)
        query_payload = _composite_query_for_aggregate(resource, metrics, kwargs)
        if query_payload:
            meta = query_payload.get("meta") or {}
            ref = meta.get("result_ref")
            if ref:
                input = {"result_ref": ref}
            elif query_payload.get("rows"):
                input = {
                    "schema": query_payload["schema"],
                    "rows": query_payload["rows"],
                }

    if not input:
        return _aggregate_input_required_message(last_result_ref=last_result_ref)
    if not metrics:
        return "Error: metrics is required"
    try:
        spec = AggregateSpec(
            input=input,
            metrics=metrics,
            dimensions=dimensions,
            window=window,
            resource=resource,
        )
        result = execute_aggregate(spec)
        if kwargs.get("_auto_input"):
            result.setdefault("meta", {})["auto_input"] = True
        return _json_result(result)
    except DataResourceError as exc:
        return f"Error: {exc}"
    except Exception as exc:
        return f"Error: aggregate_data failed: {exc}"
