from __future__ import annotations

import json
from typing import Any

from data.enrich import EnrichSpec, execute_enrich
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
    session_id = kwargs.pop("_session_id", None)
    kwargs.pop("_current_user_turn", None)
    kwargs.pop("_analysis_context", None)
    try:
        from data.schema_cache import get_cached_schema, put_cached_schema

        resource, kwargs, notes = normalize_query_resource(resource, kwargs)
        resolve = _resolve_params_with_context(kwargs, filter_context, resource=resource)
        validate_resolve_params(resource, resolve)
        cached = get_cached_schema(
            str(session_id) if session_id else None,
            resource,
            resolve,
        )
        if cached is not None:
            payload = dict(cached)
            payload["meta"] = dict(payload.get("meta") or {})
            payload["meta"]["schema_cache"] = "hit"
            if notes:
                payload["normalization_notes"] = notes
            return _json_result(payload)
        payload = inspect_resource(
            resource,
            resolve_params=resolve,
            data_dir=kwargs.get("data_dir"),
        )
        if notes:
            payload["normalization_notes"] = notes
        put_cached_schema(
            str(session_id) if session_id else None,
            resource,
            payload,
            resolve,
        )
        payload = dict(payload)
        payload["meta"] = {"schema_cache": "miss"}
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
    session_id = kwargs.pop("_session_id", None)
    for _k in (
        "_current_user_turn",
        "_analysis_context",
        "_last_result_ref",
        "_canonical_result_ref",
        "_turn_snapshots",
        "_llm_client",
        "_binding_error",
        "_binding_decision",
        "_auto_input",
        "_ref_corrected",
        "_ref_corrected_from",
        "_bind_layer",
        "_binding_trace",
    ):
        kwargs.pop(_k, None)
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

        from data.query_reuse import (
            build_query_fingerprints,
            find_reusable_dataset,
            load_reused_payload,
        )

        exact_fp, core_fp, select_cols, lim = build_query_fingerprints(
            resource=resource,
            resolve_params=resolve,
            where=where,
            select=select,
            group_by=group_by,
            order_by=order_by,
            limit=limit,
        )
        reused_rec = find_reusable_dataset(
            str(session_id) if session_id else None,
            exact_fp=exact_fp,
            core_fp=core_fp,
            select_cols=select_cols,
            limit=lim,
        )
        if reused_rec is not None:
            reused_payload = load_reused_payload(reused_rec)
            if reused_payload is not None:
                notes = notes + scope_notes
                _enrich_query_payload(reused_payload, notes)
                meta = reused_payload.setdefault("meta", {})
                meta["query_fingerprint"] = exact_fp
                meta["query_core_fingerprint"] = core_fp
                if select_cols is not None:
                    meta["select_cols"] = select_cols
                return _json_result(reused_payload)

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
        meta = result.setdefault("meta", {})
        meta["query_fingerprint"] = exact_fp
        meta["query_core_fingerprint"] = core_fp
        if select_cols is not None:
            meta["select_cols"] = select_cols
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
    order_by: list[dict] | None = None,
    limit: int | None = None,
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
    session_id = kwargs.pop("_session_id", None)
    kwargs.pop("_canonical_result_ref", None)
    kwargs.pop("_last_result_ref", None)
    kwargs.pop("_bind_layer", None)
    kwargs.pop("_current_user_turn", None)
    kwargs.pop("_teacher_message", None)

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
            order_by=order_by,
            limit=limit,
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
        if exc.param in ("dimensions", "metrics", "window") or "列/字段不存在" in str(exc):
            next_tool, example = _aggregate_missing_column_guidance(
                session_id=session_id,
                input_spec=input,
                exc=exc,
                metrics=metrics,
                dimensions=dimensions,
            )
            return _format_data_error(exc, next_tool=next_tool, example=example)
        return _format_data_error(
            exc,
            next_tool="inspect_schema",
            example="先 inspect_schema(resource=...) 确认列名，再检查 metrics/dimensions。",
        )
    except Exception as exc:
        return f"Error: aggregate_data failed: {exc}"


def _aggregate_missing_column_guidance(
    *,
    session_id: str | None,
    input_spec: dict | None,
    exc: InvalidParameterError,
    metrics: list[dict] | None,
    dimensions: list[str] | None,
) -> tuple[str, str]:
    import ast

    from data.dataset_registry import find_dataset_by_ref, get_dataset_record
    from data.lineage import (
        fields_needed,
        format_missing_column_redirect,
        prefer_row_parent_for_missing,
    )

    missing: list[str] = []
    text = str(exc)
    if "列/字段不存在:" in text:
        try:
            raw = text.split("列/字段不存在:", 1)[1].split("|", 1)[0].strip()
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, (list, tuple)):
                missing = [str(x) for x in parsed]
        except (SyntaxError, ValueError, TypeError):
            missing = []
    if not missing:
        missing = sorted(fields_needed(metrics, dimensions)) or ["(unknown)"]

    bound_id: str | None = None
    if isinstance(input_spec, dict) and session_id:
        if input_spec.get("dataset_id"):
            bound_id = str(input_spec["dataset_id"])
        elif input_spec.get("chain_from_dataset_id"):
            bound_id = str(input_spec["chain_from_dataset_id"])
        elif input_spec.get("result_ref"):
            rec = find_dataset_by_ref(session_id, str(input_spec["result_ref"]))
            if rec:
                bound_id = rec.dataset_id

    link = prefer_row_parent_for_missing(
        session_id,
        bound_dataset_id=bound_id,
        missing=missing,
    )
    bound_grain = None
    if bound_id and session_id:
        rec = get_dataset_record(session_id, bound_id)
        if rec:
            bound_grain = rec.grain

    return format_missing_column_redirect(
        base_error=text,
        link=link,
        missing=missing,
        bound_grain=bound_grain,
    )


def run_enrich_data(
    input: dict | None = None,
    lookup: str | None = None,
    on: str | dict | list | None = None,
    columns: list[str] | None = None,
    rename: dict[str, str] | None = None,
    compute_score_rate: bool | None = None,
    **kwargs: Any,
) -> str:
    """Left-join lookup resource columns onto a prior query/agg result."""
    session_id = kwargs.pop("_session_id", None)
    filter_context = _pop_filter_context(kwargs)
    kwargs.pop("_current_user_turn", None)
    kwargs.pop("_teacher_message", None)
    kwargs.pop("_canonical_result_ref", None)
    kwargs.pop("_last_result_ref", None)
    data_dir = kwargs.pop("data_dir", None)

    if not input or not isinstance(input, dict):
        return (
            "Error: enrich_data 需要 input（dataset_id 或 result_ref）。"
            " | Next: list_datasets → enrich_data"
        )
    if not lookup:
        return 'Error: lookup 必填（如 "title_info" 或 "student_info"）'
    if on is None:
        return (
            'Error: on 必填（join 键，如 "title_ID" 或 {"student_ID":"student_ID"}）'
        )

    inp = dict(input)
    if not inp.get("result_ref"):
        ds = inp.get("dataset_id") or inp.get("chain_from_dataset_id")
        if ds and session_id:
            from data.dataset_registry import resolve_dataset_id

            ref = resolve_dataset_id(session_id, str(ds))
            if not ref:
                return f"Error: 未知 dataset_id={ds!r}。请先 list_datasets。"
            inp["result_ref"] = ref
        elif not inp.get("rows"):
            return (
                "Error: input 需要 result_ref 或可解析的 dataset_id。"
                " | Next: list_datasets"
            )

    # Lookup resolve params (class/classes etc.) — title_info/student_info usually empty
    resolve_params = _resolve_params_with_context(
        kwargs,
        filter_context,
        resource=str(lookup),
    )
    try:
        validate_resolve_params(str(lookup), resolve_params)
    except Exception:
        resolve_params = _resolve_params(kwargs)

    try:
        spec = EnrichSpec(
            input=inp,
            lookup=str(lookup),
            on=on,
            columns=columns,
            rename=rename,
            resolve_params=resolve_params,
            compute_score_rate=bool(compute_score_rate)
            if compute_score_rate is not None
            else False,
        )
        result = execute_enrich(spec, data_dir=data_dir)
        meta = result.setdefault("meta", {})
        if inp.get("dataset_id"):
            meta["source_dataset_id"] = inp.get("dataset_id")
        if inp.get("result_ref"):
            meta["source_result_ref"] = inp.get("result_ref")
        return _json_result(result)
    except (DataResourceError, UnknownResourceError) as exc:
        return _format_data_error(exc, next_tool="inspect_schema")
    except InvalidParameterError as exc:
        return _format_data_error(
            exc,
            next_tool="inspect_schema / list_datasets",
            example=(
                'enrich_data(input={dataset_id}, lookup="title_info", on="title_ID", '
                'columns=["score"], rename={"score":"full_score"})'
            ),
        )
    except Exception as exc:
        return f"Error: enrich_data failed: {exc}"
