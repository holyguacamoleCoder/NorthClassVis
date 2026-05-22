import json
from typing import Any

from loop_state import AnalysisToolContext

DATA_CHAIN_TOOLS = frozenset({"query_data", "aggregate_data", "inspect_schema"})


def inject_data_tool_context(
    tool_name: str | None,
    parsed_args: dict[str, Any],
    *,
    analysis_context: AnalysisToolContext | None,
    batch_query_refs: list[str],
) -> dict[str, Any]:
    args = dict(parsed_args)
    if tool_name not in DATA_CHAIN_TOOLS:
        return args

    if tool_name == "aggregate_data" and not args.get("input"):
        if batch_query_refs:
            args["input"] = {"result_ref": batch_query_refs[-1]}
            args["_auto_input"] = True
        elif analysis_context and analysis_context.last_result_ref:
            args["input"] = {"result_ref": analysis_context.last_result_ref}
            args["_auto_input"] = True

    if analysis_context and analysis_context.last_result_ref:
        args["_last_result_ref"] = analysis_context.last_result_ref

    return args


def record_query_result(
    tool_result: str,
    *,
    analysis_context: AnalysisToolContext | None,
    batch_query_refs: list[str],
) -> None:
    if not tool_result or tool_result.startswith("Error:"):
        return
    try:
        payload = json.loads(tool_result)
    except json.JSONDecodeError:
        return
    if not isinstance(payload, dict):
        return
    ref = (payload.get("meta") or {}).get("result_ref")
    if ref:
        batch_query_refs.append(str(ref))
    if analysis_context is not None:
        analysis_context.note_query_result(payload)
