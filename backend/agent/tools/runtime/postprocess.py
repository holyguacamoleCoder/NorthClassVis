import logging

from common.logger import get_logger, log_event
from context import maybe_persist_output, track_recent_file
from context.config import DEFAULT_CONFIG
from context.state import CompactState
from context.tool_result_summary import append_query_summary_to_result
from permission import PermissionManager

from loop_state import AnalysisToolContext, QuerySnapshot
from .data_chain import record_query_result
from .repair import ToolRepairResult

_log = get_logger("tools")

PATH_TOOLS = frozenset({"read_file", "list_files"})


def prepend_repair_notes(content: str, notes: list[str]) -> str:
    if not notes:
        return content
    prefix = "\n".join(notes)
    if content:
        return f"{prefix}\n\n{content}"
    return prefix


def log_tool_repair(
    repair: ToolRepairResult,
    *,
    tool_call_id: str | None,
    permission: PermissionManager | None,
) -> None:
    if not repair.was_repaired:
        return
    mode = ""
    if permission is not None:
        mode = getattr(permission.mode, "value", permission.mode)
        if not isinstance(mode, str):
            mode = str(mode)
    log_event(
        _log,
        logging.INFO,
        "tool_repaired",
        tool_call_id=tool_call_id,
        original_tool=repair.original_name,
        canonical_tool=repair.name,
        confidence=repair.confidence,
        permission_mode=mode or None,
        notes=repair.notes,
        missing_required=sorted(repair.missing_required) or None,
    )


def postprocess_tool_result(
    tool_name: str,
    tool_result: str,
    *,
    call_id: str | None,
    parsed_args: dict,
    compact_state: CompactState | None,
    analysis_context: AnalysisToolContext | None,
    batch_snapshots: list[QuerySnapshot],
) -> str:
    if tool_name == "query_data" and isinstance(tool_result, str):
        enriched = record_query_result(
            tool_result,
            parsed_args=parsed_args,
            analysis_context=analysis_context,
            batch_snapshots=batch_snapshots,
        )
        if enriched:
            tool_result = enriched
        tool_result = append_query_summary_to_result(tool_result)

    if compact_state and tool_name in PATH_TOOLS:
        path_arg = parsed_args.get("path") or "."
        track_recent_file(
            compact_state,
            str(path_arg),
            max_files=DEFAULT_CONFIG.max_recent_files,
        )

    if call_id and isinstance(tool_result, str):
        tool_result = maybe_persist_output(call_id, tool_result)

    return tool_result
