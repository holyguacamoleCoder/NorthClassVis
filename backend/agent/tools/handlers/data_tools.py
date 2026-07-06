from __future__ import annotations

import json
from typing import Any

from data.aggregate import AggregateSpec, execute_aggregate
from data.dataset_registry import build_datasets_catalog
from data.exceptions import DataResourceError, InvalidParameterError, UnknownResourceError
from data.filter_context import FilterContext
from data.inspect import inspect_resource
from data.param_validation import (
    normalize_query_resource,
    repair_submit_record_week_usage,
    validate_resolve_params,
)
from data.query import QuerySpec, execute_query
from data.where import repair_where
from data.result_hints import enrich_aggregate_payload, enrich_query_payload, normalize_limit

_RESOLVE_KEYS = frozenset({"class", "classes", "majors", "week_range", "student_ids"})

# Substring matched by loop_guards when aggregate_data fails without input.
AGGREGATE_INPUT_REQUIRED_MARKER = "aggregate_data 需要 input"


def _format_data_error(
    exc: Exception,
    *,
    next_tool: str | None = None,
    example: str | None = None,
) -> str:
    msg = f"Error: {exc}"
    if isinstance(exc, InvalidParameterError) and exc.param:
        msg += f" (param={exc.param})"
    if next_tool:
        msg += f" | Next: {next_tool}"
    if example:
        msg += f" | Example: {example}"
    return msg


def _resolve_params(kwargs: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in kwargs.items() if k in _RESOLVE_KEYS and v is not None}


def _resolve_params_with_context(
    kwargs: dict[str, Any],
    filter_context: FilterContext | None,
    *,
    resource: str | None = None,
    teacher_message: str | None = None,
    scope_notes: list[str] | None = None,
) -> dict[str, Any]:
    resolve = _resolve_params(kwargs)
    if filter_context is not None:
        resolve = filter_context.merge_resolve_params(
            resolve,
            resource_id=resource,
            teacher_message=teacher_message,
            data_dir=kwargs.get("data_dir"),
            scope_notes=scope_notes,
        )
    return resolve


def _pop_filter_context(kwargs: dict[str, Any]) -> FilterContext | None:
    raw = kwargs.pop("_filter_context", None)
    if isinstance(raw, FilterContext):
        return raw
    if isinstance(raw, dict):
        return FilterContext.from_dict(raw)
    return None


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
                    {"op": "count_distinct", "field": "student_ID", "as": "students"},
                    {"op": "mean", "field": "score", "as": "avg_score"},
                ],
            },
        }
    if notes:
        meta["normalization_notes"] = notes
    return payload


def _aggregate_input_required_message() -> str:
    return (
        "Error: aggregate_data 需要 input（含 result_ref、dataset_id 或 inline schema+rows）。"
        "请先对本题调用 query_data，再使用返回的 meta.result_ref / meta.dataset_id；"
        "续算切片请 bind='chain' 或 chain_from_dataset_id。"
    )


def run_resolve_dataset_binding(
    metrics: list[dict] | None = None,
    input: dict | None = None,
    bind: str | None = None,
    **kwargs: Any,
) -> str:
    """Expose semantic binding for the main model (optional step before aggregate_data)."""
    from tools.runtime.binding import (
        build_binding_context,
        check_ambiguity,
        resolve_binding_intent,
        validate_decision,
    )

    session_id = kwargs.pop("_session_id", None)
    current_turn = kwargs.pop("_current_user_turn", None)
    llm_client = kwargs.pop("_llm_client", None)
    snapshots = kwargs.pop("_turn_snapshots", None)
    teacher_message = kwargs.pop("_teacher_message", None)

    if not session_id:
        return "Error: resolve_dataset_binding 需要有效会话（先在本 session 内 query_data）。"

    from loop_state import AnalysisToolContext, QuerySnapshot

    ctx_obj = AnalysisToolContext(
        session_id=str(session_id),
        user_turn=int(current_turn) if current_turn is not None else 0,
        current_user_message=str(teacher_message).strip() if teacher_message else None,
        turn_snapshots=list(snapshots or []),
    )
    batch: list[QuerySnapshot] = []

    bctx = build_binding_context(
        inp=dict(input or {}),
        metrics=list(metrics or []),
        dimensions=None,
        bind=bind,
        analysis_context=ctx_obj,
        batch_snapshots=batch,
    )
    gate = check_ambiguity(bctx)
    decision = resolve_binding_intent(bctx, llm_client)
    payload: dict[str, Any] = {
        "gate": {"triggered": gate.triggered, "reasons": gate.reasons},
        "decision": None,
    }
    if decision:
        err = validate_decision(decision, bctx)
        if err:
            payload["error"] = err
        else:
            payload["decision"] = {
                "scope": decision.scope,
                "dataset_id": decision.dataset_id,
                "result_ref": decision.result_ref,
                "confidence": decision.confidence,
                "rationale": decision.rationale,
                "resolver": decision.resolver,
            }
            payload["next_step"] = {
                "tool": "aggregate_data",
                "example": {
                    "input": {"dataset_id": decision.dataset_id},
                    "metrics": metrics or [],
                },
            }
    elif not gate.triggered and len(bctx.candidates) == 1:
        c = bctx.candidates[0]
        payload["decision"] = {
            "scope": "single_candidate",
            "dataset_id": c.dataset_id,
            "result_ref": c.result_ref,
            "resolver": "rule",
        }
    else:
        payload["error"] = (
            "无法解析绑定；请 list_datasets 或补充 query_data 后重试。"
        )
    return _json_result(payload)


def run_list_datasets(
    tail: int = 20,
    user_turn: int | None = None,
    **kwargs: Any,
) -> str:
    session_id = kwargs.pop("_session_id", None)
    current_turn = kwargs.pop("_current_user_turn", None)
    try:
        tail_n = max(1, min(int(tail), 50))
    except (TypeError, ValueError):
        return "Error: tail must be an integer between 1 and 50."
    turn_filter: int | None = None
    if user_turn is not None:
        try:
            turn_filter = int(user_turn)
        except (TypeError, ValueError):
            return "Error: user_turn must be an integer."
    if not session_id:
        return (
            "Error: list_datasets 需要有效会话。"
            "请在本 session 内先执行 query_data，或确认 agent 已绑定 session_id。"
        )
    payload = build_datasets_catalog(
        str(session_id),
        tail=tail_n,
        user_turn=turn_filter,
        current_user_turn=int(current_turn) if current_turn is not None else None,
    )
    return _json_result(payload)


def run_inspect_schema(resource: str | None = None, **kwargs: Any) -> str:
    if not resource:
        return (
            "Error: resource is required | Next: inspect_schema with resource from "
            "resource_registry (e.g. student_info, submit_record)"
        )
    filter_context = _pop_filter_context(kwargs)
    try:
        resource, kwargs, notes = normalize_query_resource(resource, kwargs)
        resolve = _resolve_params_with_context(kwargs, filter_context, resource=resource)
        validate_resolve_params(resource, resolve)
        payload = inspect_resource(
            resource,
            resolve_params=resolve,
            data_dir=kwargs.get("data_dir"),
        )
        if notes:
            payload["normalization_notes"] = notes
        return _json_result(payload)
    except UnknownResourceError as exc:
        return _format_data_error(
            exc,
            next_tool="inspect_schema",
            example='resource="student_info"',
        )
    except InvalidParameterError as exc:
        hint = "query_data with the same resource and class/classes"
        if exc.param in ("class", "classes"):
            hint = 'inspect_schema(resource="submit_record", class="Class1")'
        return _format_data_error(exc, next_tool=hint)
    except DataResourceError as exc:
        return _format_data_error(exc, next_tool="inspect_schema")
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
        return (
            "Error: resource is required | Next: query_data with resource and required "
            "class/classes (see inspect_schema or resource_registry)"
        )
    if where is None and filter is not None:
        where = filter
    where_repair_notes: list[str] = []
    if where is not None:
        where, where_repair_notes = repair_where(where)
    filter_context = _pop_filter_context(kwargs)
    teacher_message = kwargs.pop("_teacher_message", None)
    limit_notes: list[str] = []
    scope_notes: list[str] = []
    try:
        limit, limit_note = normalize_limit(limit)
        if limit_note:
            limit_notes.append(limit_note)
        resource, kwargs, notes = normalize_query_resource(resource, kwargs, where=where)
        resource, kwargs, where, group_by, order_by, week_notes = repair_submit_record_week_usage(
            resource,
            kwargs,
            where=where,
            group_by=group_by,
            order_by=order_by,
        )
        notes = list(notes) + week_notes + limit_notes + where_repair_notes
        resolve = _resolve_params_with_context(
            kwargs,
            filter_context,
            resource=resource,
            teacher_message=teacher_message,
            scope_notes=scope_notes,
        )
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
        result = execute_query(
            spec,
            filter_context=filter_context,
            teacher_message=teacher_message,
            data_dir=kwargs.get("data_dir"),
        )
        notes = notes + scope_notes
        _enrich_query_payload(result, notes)
        enrich_query_payload(
            result,
            resource=resource,
            group_by=group_by,
            limit=limit,
        )
        return _json_result(result)
    except UnknownResourceError as exc:
        return _format_data_error(exc, next_tool="inspect_schema")
    except InvalidParameterError as exc:
        next_tool = "inspect_schema"
        example = None
        if exc.param in ("where", "group_by", "order_by", "select"):
            next_tool = "inspect_schema then fix field names / resource"
            if "week_aggregation" in str(exc) or "week_index" in str(exc) or "week" in str(exc).lower():
                example = (
                    'resource="week_aggregation", classes=["Class2"], week_range=[13, 15]'
                )
        elif exc.param == "limit":
            next_tool = "query_data"
            example = 'omit limit for full scan; or limit>=1 for preview'
        elif exc.param in ("class", "classes"):
            example = 'resource="submit_record", class="Class1", majors=["J23517"]'
        return _format_data_error(exc, next_tool=next_tool, example=example)
    except DataResourceError as exc:
        return _format_data_error(exc, next_tool="inspect_schema")
    except Exception as exc:
        return f"Error: query_data failed: {exc}"


def _composite_query_for_aggregate(
    resource: str,
    metrics: list[dict],
    kwargs: dict[str, Any],
    *,
    filter_context: FilterContext | None = None,
) -> dict | None:
    """When aggregate omits input but passes resource + filters, run query first."""
    resolve = _resolve_params_with_context(kwargs, filter_context, resource=resource)
    if resource == "submit_record" and not resolve.get("class") and not resolve.get("classes"):
        return None
    fields = {m.get("field") for m in metrics if m.get("field")}
    select = [f for f in fields if f] or None
    extra = {k: v for k, v in kwargs.items() if k in _RESOLVE_KEYS or k == "class"}
    raw = run_query_data(
        resource=resource,
        select=select,
        limit=kwargs.get("limit"),
        data_dir=kwargs.get("data_dir"),
        _filter_context=filter_context,
        **extra,
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
    bind: str | None = None,
    **kwargs: Any,
) -> str:
    binding_error = kwargs.pop("_binding_error", None)
    if binding_error:
        return str(binding_error)

    ref_corrected = bool(kwargs.pop("_ref_corrected", False))
    ref_corrected_from = kwargs.pop("_ref_corrected_from", None)
    binding_decision = kwargs.pop("_binding_decision", None)
    binding_trace = kwargs.pop("_binding_trace", None)
    auto_input = bool(kwargs.pop("_auto_input", False))
    filter_context = _pop_filter_context(kwargs)
    kwargs.pop("_canonical_result_ref", None)
    kwargs.pop("_last_result_ref", None)
    kwargs.pop("_bind_layer", None)

    if not input and resource and metrics:
        resource, kwargs, _notes = normalize_query_resource(resource, kwargs)
        query_payload = _composite_query_for_aggregate(
            resource,
            metrics,
            kwargs,
            filter_context=filter_context,
        )
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
        return _aggregate_input_required_message()
    if not metrics:
        return (
            'Error: metrics is required | Example: metrics=[{"op":"count","as":"n"},'
            ' {"op":"mean","field":"score","as":"avg"}]'
        )
    try:
        spec = AggregateSpec(
            input=input,
            metrics=metrics,
            dimensions=dimensions,
            window=window,
            resource=resource,
        )
        result = execute_aggregate(spec)
        meta = result.setdefault("meta", {})
        if auto_input:
            meta["auto_input"] = True
        if binding_decision:
            meta["binding_decision"] = binding_decision
        if binding_trace:
            meta["binding_trace"] = binding_trace
        if ref_corrected:
            meta["ref_corrected"] = True
        enrich_aggregate_payload(
            result,
            metrics=metrics,
            input_spec=input,
            ref_corrected=ref_corrected,
            ref_corrected_from=str(ref_corrected_from) if ref_corrected_from else None,
            binding_decision=str(binding_decision) if binding_decision else None,
        )
        return _json_result(result)
    except DataResourceError as exc:
        return _format_data_error(exc, next_tool="query_data then aggregate_data")
    except InvalidParameterError as exc:
        return _format_data_error(
            exc,
            next_tool="inspect_schema",
            example='先 inspect_schema(resource=...) 确认列名，再 query_data → aggregate_data',
        )
    except Exception as exc:
        return f"Error: aggregate_data failed: {exc}"
