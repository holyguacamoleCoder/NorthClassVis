"""Inject session/binding context into data tool dispatch args."""

from __future__ import annotations

from typing import Any

from data.filter_context import FilterContext
from loop_state import AnalysisToolContext, QuerySnapshot

from ..binding.pipeline import resolve_aggregate_binding
from ..binding.types import BindMode
from .snapshot import working_result_ref
from .types import ADAPTER_CONTEXT_TOOLS, DATA_CHAIN_TOOLS


def inject_data_tool_context(
    tool_name: str | None,
    parsed_args: dict[str, Any],
    *,
    analysis_context: AnalysisToolContext | None,
    batch_snapshots: list[QuerySnapshot],
    llm_client: Any | None = None,
    filter_context: FilterContext | None = None,
) -> dict[str, Any]:
    args = dict(parsed_args)
    if tool_name == "review_report" and analysis_context is not None:
        args["_analysis_context"] = analysis_context
    if tool_name in ADAPTER_CONTEXT_TOOLS and filter_context is not None:
        args["_filter_context"] = filter_context

    if tool_name not in DATA_CHAIN_TOOLS:
        return args

    if tool_name in ("query_data", "inspect_schema", "aggregate_data") and filter_context is not None:
        args["_filter_context"] = filter_context

    if analysis_context:
        if analysis_context.session_id:
            args["_session_id"] = analysis_context.session_id
        args["_current_user_turn"] = analysis_context.user_turn
        if analysis_context.current_user_message:
            args["_teacher_message"] = analysis_context.current_user_message
        if tool_name in ("list_datasets", "resolve_dataset_binding"):
            args["_turn_snapshots"] = list(analysis_context.turn_snapshots)
            if llm_client is not None:
                args["_llm_client"] = llm_client

    if tool_name in ("list_datasets", "resolve_dataset_binding"):
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
