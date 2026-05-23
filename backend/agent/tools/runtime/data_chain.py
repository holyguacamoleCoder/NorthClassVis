"""Memory (working set) + disk (catalog) binding for query_data → aggregate_data."""



from __future__ import annotations



import json

import time

from dataclasses import dataclass

from typing import Any



from data.dataset_registry import (

    DatasetRecord,

    append_dataset,

    find_dataset_by_ref,

    format_catalog_hint,

    get_dataset_record,

    new_dataset_id,

    resolve_dataset_id,

)

from loop_state import AnalysisToolContext, QuerySnapshot



from .binding_compat import BindMode, BindingCandidate



DATA_CHAIN_TOOLS = frozenset(
    {
        "query_data",
        "aggregate_data",
        "inspect_schema",
        "list_datasets",
        "resolve_dataset_binding",
    }
)





def _normalize_result_ref(ref: str) -> str:

    return str(ref).strip().replace("\\", "/")





@dataclass

class AggregateBinding:

    result_ref: str | None = None

    dataset_id: str | None = None

    error: str | None = None

    decision: str | None = None

    corrected: bool = False

    corrected_from: str | None = None

    auto_input: bool = False
    trace: dict[str, Any] | None = None





def _snap_to_candidate(snap: QuerySnapshot, user_turn: int) -> BindingCandidate:

    return BindingCandidate(

        result_ref=snap.result_ref,

        result_rows=snap.result_rows,

        user_turn=user_turn,

        query_limit=snap.query_limit,

        rows_scanned=snap.rows_scanned,

        dataset_id=snap.dataset_id,

        resource=snap.resource,

    )





def _record_to_candidate(rec: DatasetRecord) -> BindingCandidate:

    return BindingCandidate(

        result_ref=rec.result_ref,

        result_rows=rec.result_rows,

        user_turn=rec.user_turn,

        query_limit=rec.query_limit,

        rows_scanned=rec.rows_scanned,

        dataset_id=rec.dataset_id,

        resource=rec.resource,

    )





def _collect_turn_candidates(

    analysis_context: AnalysisToolContext | None,

    batch_snapshots: list[QuerySnapshot],

) -> list[BindingCandidate]:

    """本 user_turn 内 query 候选（批内 + 工作集），去重保序。"""

    if analysis_context is None:

        turn = 0

    else:

        turn = analysis_context.user_turn



    combined = list(analysis_context.turn_snapshots if analysis_context else []) + list(
        batch_snapshots
    )
    ordered: list[QuerySnapshot] = []
    seen: set[str] = set()
    for snap in combined:
        key = _normalize_result_ref(snap.result_ref)
        if key in seen:
            ordered = [s for s in ordered if _normalize_result_ref(s.result_ref) != key]
        else:
            seen.add(key)
        ordered.append(snap)

    return [_snap_to_candidate(s, turn) for s in ordered]





def _lookup_explicit_candidate(

    result_ref: str,

    *,

    session_id: str | None,

    turn_candidates: list[BindingCandidate],

) -> BindingCandidate | None:

    norm = _normalize_result_ref(result_ref)

    for c in turn_candidates:

        if _normalize_result_ref(c.result_ref) == norm:

            return c

    if session_id:

        rec = find_dataset_by_ref(session_id, result_ref)

        if rec:

            return _record_to_candidate(rec)

    return None





def resolve_aggregate_binding(
    inp: dict[str, Any],
    *,
    metrics: list[dict[str, Any]],
    dimensions: list[str] | None,
    bind: BindMode,
    analysis_context: AnalysisToolContext | None,
    batch_snapshots: list[QuerySnapshot],
    llm_client: Any | None = None,
) -> AggregateBinding:
    from .binding_pipeline import resolve_aggregate_binding_pipeline

    return resolve_aggregate_binding_pipeline(
        inp,
        metrics=metrics,
        dimensions=dimensions,
        bind=bind,
        analysis_context=analysis_context,
        batch_snapshots=batch_snapshots,
        llm_client=llm_client,
    )


def working_result_ref(

    batch_snapshots: list[QuerySnapshot],

    analysis_context: AnalysisToolContext | None,

) -> str | None:

    """本回合最后一次 query 的 ref（仅供提示，不作跨 turn 自动绑定）。"""

    if batch_snapshots:

        return batch_snapshots[-1].result_ref

    if analysis_context and analysis_context.working_active_ref:

        return analysis_context.working_active_ref

    return None





def inject_data_tool_context(

    tool_name: str | None,

    parsed_args: dict[str, Any],

    *,

    analysis_context: AnalysisToolContext | None,
    batch_snapshots: list[QuerySnapshot],
    llm_client: Any | None = None,
) -> dict[str, Any]:

    args = dict(parsed_args)

    if tool_name not in DATA_CHAIN_TOOLS:

        return args

    if tool_name in ("list_datasets", "resolve_dataset_binding"):
        if analysis_context:
            if analysis_context.session_id:
                args["_session_id"] = analysis_context.session_id
            args["_current_user_turn"] = analysis_context.user_turn
            if analysis_context.current_user_message:
                args["_teacher_message"] = analysis_context.current_user_message
            args["_turn_snapshots"] = list(analysis_context.turn_snapshots)
            if llm_client is not None:
                args["_llm_client"] = llm_client
        return args

    if tool_name == "aggregate_data":

        inp = args.get("input")

        if not isinstance(inp, dict):

            inp = {}

        metrics = args.get("metrics") if isinstance(args.get("metrics"), list) else []

        dimensions = args.get("dimensions") if isinstance(args.get("dimensions"), list) else None

        bind = BindMode.parse(args.get("bind"))



        binding = resolve_aggregate_binding(
            inp,
            metrics=metrics,
            dimensions=dimensions,
            bind=bind,
            analysis_context=analysis_context,
            batch_snapshots=batch_snapshots,
            llm_client=llm_client,
        )



        if binding.error:

            args["_binding_error"] = binding.error

        elif binding.result_ref:

            new_inp = {**inp, "result_ref": binding.result_ref}

            if binding.dataset_id and "dataset_id" not in new_inp:

                new_inp["dataset_id"] = binding.dataset_id

            args["input"] = new_inp

            args["_binding_decision"] = binding.decision

            if binding.auto_input:

                args["_auto_input"] = True

            if binding.corrected:
                args["_ref_corrected"] = True
                args["_ref_corrected_from"] = binding.corrected_from
                args["_bind_layer"] = binding.decision
            if binding.trace:
                args["_binding_trace"] = binding.trace

    working = working_result_ref(batch_snapshots, analysis_context)

    if analysis_context and analysis_context.working_active_ref:

        args["_last_result_ref"] = analysis_context.working_active_ref

    if working:

        args["_canonical_result_ref"] = working



    return args





def record_query_result(

    tool_result: str,

    *,

    parsed_args: dict[str, Any] | None = None,

    analysis_context: AnalysisToolContext | None = None,

    batch_snapshots: list[QuerySnapshot],

) -> str | None:

    if not tool_result or tool_result.startswith("Error:"):

        return None

    try:

        payload = json.loads(tool_result)

    except json.JSONDecodeError:

        return None

    if not isinstance(payload, dict):

        return None

    ref = (payload.get("meta") or {}).get("result_ref")

    if not ref:

        return None



    query_limit = _limit_from_args_or_meta(parsed_args, payload)

    meta = payload.get("meta") or {}

    stored_rows = _stored_row_count(payload, str(ref))



    dataset_id = new_dataset_id()

    snap = QuerySnapshot(

        result_ref=str(ref),

        result_rows=stored_rows,

        query_limit=query_limit,

        rows_scanned=_safe_int(meta.get("rows_scanned")),

        resource=meta.get("resource"),

        dataset_id=dataset_id,

    )

    batch_snapshots.append(snap)



    if analysis_context is not None:

        analysis_context.register_query_snapshot(snap)

        classes = None

        if parsed_args:

            c = parsed_args.get("classes") or parsed_args.get("class")

            if isinstance(c, list):

                classes = c

            elif c:

                classes = [str(c)]

        append_dataset(

            analysis_context.session_id,

            DatasetRecord(

                dataset_id=dataset_id,

                result_ref=snap.result_ref,

                user_turn=analysis_context.user_turn,

                resource=snap.resource,

                result_rows=snap.result_rows,

                query_limit=snap.query_limit,

                rows_scanned=snap.rows_scanned,

                classes=classes,

                created_at=time.time(),

            ),

        )

        meta_out = payload.setdefault("meta", {})

        meta_out["dataset_id"] = dataset_id

        meta_out["storage_layer"] = "disk"

        meta_out["working_ref"] = snap.result_ref

    return json.dumps(payload, ensure_ascii=False, default=str)





def _limit_from_args_or_meta(

    parsed_args: dict[str, Any] | None,

    payload: dict,

) -> int | None:

    if parsed_args is not None and parsed_args.get("limit") is not None:

        try:

            return int(parsed_args["limit"])

        except (TypeError, ValueError):

            pass

    meta = payload.get("meta") or {}

    if meta.get("query_limit") is not None:

        try:

            return int(meta["query_limit"])

        except (TypeError, ValueError):

            pass

    return None





def _stored_row_count(payload: dict, ref: str) -> int:

    rows = payload.get("rows")

    preview_rows = len(rows) if isinstance(rows, list) else 0

    meta = payload.get("meta") or {}

    if not meta.get("truncated"):

        return preview_rows

    try:

        from data.result_store import load_result



        full = load_result(ref)

        return len(full.get("rows") or [])

    except (FileNotFoundError, OSError, TypeError, ValueError):

        return preview_rows





def _safe_int(value: Any) -> int | None:

    if value is None:

        return None

    try:

        return int(value)

    except (TypeError, ValueError):

        return None





def partition_tool_calls_for_data_pipeline(

    tool_calls: list[dict[str, Any]],

) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:

    """先执行 query_data（写入内存+硬盘），再执行其余（含 aggregate）。"""

    queries: list[dict[str, Any]] = []

    rest: list[dict[str, Any]] = []

    for call in tool_calls:

        if call.get("name") == "query_data":

            queries.append(call)

        else:

            rest.append(call)

    return queries, rest


