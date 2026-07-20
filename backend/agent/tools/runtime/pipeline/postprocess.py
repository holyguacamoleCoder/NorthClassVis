import json
import logging
from typing import Any

from common.logger import get_logger, log_event
from context import maybe_persist_output, track_recent_file
from context.config import DEFAULT_CONFIG
from context.state import CompactState
from context.tool_result_summary import append_query_summary_to_result
from loop_state import AnalysisToolContext, QuerySnapshot
from permission import PermissionManager

from ..data.snapshot import record_query_result
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
    filter_context: Any | None = None,
) -> str:
    if tool_name == "query_data" and isinstance(tool_result, str):
        enriched = record_query_result(
            tool_result,
            parsed_args=parsed_args,
            analysis_context=analysis_context,
            batch_snapshots=batch_snapshots,
            tool_name=tool_name,
        )
        if enriched:
            tool_result = enriched
        tool_result = append_query_summary_to_result(tool_result)

    if tool_name == "aggregate_data" and isinstance(tool_result, str):
        enriched = record_query_result(
            tool_result,
            parsed_args=parsed_args,
            analysis_context=analysis_context,
            batch_snapshots=batch_snapshots,
            tool_name=tool_name,
        )
        if enriched:
            tool_result = enriched
        tool_result = append_query_summary_to_result(tool_result)

    if tool_name == "enrich_data" and isinstance(tool_result, str):
        enriched = record_query_result(
            tool_result,
            parsed_args=parsed_args,
            analysis_context=analysis_context,
            batch_snapshots=batch_snapshots,
            tool_name=tool_name,
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

    if call_id and isinstance(tool_result, str) and tool_name not in (
        "load_skill",
        "load_reference",
    ):
        tool_result = maybe_persist_output(call_id, tool_result)

    if tool_name == "build_visual_links" and isinstance(tool_result, str):
        _maybe_register_visual_links(tool_result, analysis_context=analysis_context)

    if tool_name in ("query_data", "aggregate_data", "enrich_data") and isinstance(
        tool_result, str
    ):
        tool_result = _append_datasets_session_snapshot(
            tool_result, analysis_context=analysis_context
        )

    if tool_name in ("write_file", "edit_file") and isinstance(tool_result, str):
        _maybe_record_session_deliverable(
            tool_result,
            parsed_args=parsed_args,
            analysis_context=analysis_context,
        )
        tool_result = _append_deliverables_session_snapshot(
            tool_result, analysis_context=analysis_context
        )
        tool_result = _maybe_append_report_validation(
            tool_result,
            parsed_args=parsed_args,
            analysis_context=analysis_context,
            filter_context=filter_context,
        )

    return tool_result


def _append_datasets_session_snapshot(
    tool_result: str,
    *,
    analysis_context: AnalysisToolContext | None,
) -> str:
    if not analysis_context or not analysis_context.session_id:
        return tool_result
    if (tool_result or "").strip().startswith("Error:"):
        return tool_result
    try:
        from data.dataset_registry import format_catalog_hint

        hint = (format_catalog_hint(analysis_context.session_id, tail=5) or "").strip()
    except Exception:
        return tool_result
    if not hint:
        return tool_result
    return f"{tool_result.rstrip()}\n\n---\n[session_snapshot]\ndatasets:\n{hint}"


def _append_deliverables_session_snapshot(
    tool_result: str,
    *,
    analysis_context: AnalysisToolContext | None,
) -> str:
    if not analysis_context or not analysis_context.session_id:
        return tool_result
    try:
        from session.deliverables_registry import format_deliverables_prompt

        block = (format_deliverables_prompt(analysis_context.session_id, tail=5) or "").strip()
    except Exception:
        return tool_result
    if not block:
        return tool_result
    return f"{tool_result.rstrip()}\n\n---\n[session_snapshot]\n{block}"


def _maybe_register_visual_links(
    tool_result: str,
    *,
    analysis_context: AnalysisToolContext | None,
) -> None:
    if not analysis_context or not (tool_result or "").strip():
        return
    try:
        payload = json.loads(tool_result)
    except json.JSONDecodeError:
        return
    if not isinstance(payload, dict):
        return
    links = payload.get("visual_links")
    if isinstance(links, list):
        analysis_context.register_visual_links(links)


def _maybe_append_report_validation(
    tool_result: str,
    *,
    parsed_args: dict,
    analysis_context: AnalysisToolContext | None,
    filter_context: Any | None = None,
) -> str:
    if not (tool_result or "").strip().startswith("["):
        return tool_result
    if "OK" not in tool_result:
        return tool_result
    from report_delivery import parse_deliverable_path_from_tool_content
    from permission.paths import normalize_path
    from common.paths import DATA_DIR
    from report.finalize import normalize_report_deliverable
    from report.validate import format_validation_for_tool_result, validate_report

    rel = parse_deliverable_path_from_tool_content(tool_result) or str(
        parsed_args.get("path") or ""
    ).strip()
    if not rel:
        return tool_result
    rel_norm = normalize_path(rel)
    if not rel_norm.startswith("reports/") or not rel_norm.endswith(".md"):
        return tool_result
    full = (DATA_DIR / rel_norm).resolve()
    if not full.is_file():
        return tool_result
    try:
        text_on_disk = full.read_text(encoding="utf-8")
        links = (
            analysis_context.session_visual_links
            if analysis_context is not None
            else None
        )
        # Validate against a normalized preview only — do not mutate other sections on disk.
        preview, normalize_notes = normalize_report_deliverable(
            text_on_disk,
            session_visual_links=links,
            filter_context=filter_context,
        )

        result = validate_report(
            preview,
            path=rel_norm,
            analysis_context=analysis_context,
            validation_level="draft",
        )
        block = format_validation_for_tool_result(result)
        prefix = tool_result.rstrip()
        if normalize_notes:
            hint = ", ".join(normalize_notes[:3])
            if len(normalize_notes) > 3:
                hint += f" …+{len(normalize_notes) - 3}"
            prefix = (
                f"{prefix}\n[Report hint] 交付时将自动：{hint}"
                "（本次 edit 未改写磁盘上的其他章节）"
            )
        return f"{prefix}\n\n{block}"
    except Exception:
        _log.exception("report_validate_failed")
        return tool_result


def _maybe_record_session_deliverable(
    tool_result: str,
    *,
    parsed_args: dict,
    analysis_context: AnalysisToolContext | None,
) -> None:
    if not (tool_result or "").strip().startswith("["):
        return
    if "OK" not in tool_result:
        return
    from report_delivery import parse_deliverable_path_from_tool_content, deliverable_label
    from session.deliverables_registry import record_deliverable_from_tool

    rel = parse_deliverable_path_from_tool_content(tool_result) or str(parsed_args.get("path") or "").strip()
    if not rel:
        return
    session_id = analysis_context.session_id if analysis_context else None
    user_turn = analysis_context.user_turn if analysis_context else 0
    try:
        record_deliverable_from_tool(
            session_id,
            rel_path=rel,
            label=deliverable_label(rel),
            user_turn=user_turn,
        )
    except Exception:
        _log.exception("record_deliverable_failed")
