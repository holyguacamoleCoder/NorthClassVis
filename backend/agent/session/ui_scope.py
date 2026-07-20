"""Augment user turns with UI-synced analysis scope (scatter selection, nav filters)."""

from __future__ import annotations

import re
from typing import Any

from common.prompts import format_filter_context_section
from data.filter_context import FilterContext

_SELECTION_INTENT = re.compile(
    r"我选|选的|选中|这几|这批|所选|选中的|已经选择|选择了|选了|selected",
    re.IGNORECASE,
)


def teacher_has_selection_intent(message: str | None) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    return bool(_SELECTION_INTENT.search(text))


def augment_user_message_with_ui_scope(
    content: str,
    fc: FilterContext | None,
) -> str:
    """
    Legacy text injection disabled.

    Scope is carried via HTTP ``filter_context`` / composer scope chip (``ui_scope``),
    not appended into the teacher-visible user message.
    """
    return content


def _clean_str_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(x).strip() for x in value if str(x).strip()]


def _nav_summary_from_ui_scope(ui_scope: dict[str, Any] | None) -> dict[str, Any] | None:
    """Build a format_filter_context_section-compatible summary from chip ui_scope."""
    if not isinstance(ui_scope, dict):
        return None
    ids = _clean_str_list(ui_scope.get("selected_student_ids"))
    classes = _clean_str_list(ui_scope.get("classes"))
    majors = _clean_str_list(ui_scope.get("majors"))
    week = None
    wr = ui_scope.get("week_range")
    if isinstance(wr, (list, tuple)) and len(wr) >= 2:
        try:
            week = [int(wr[0]), int(wr[1])]
        except (TypeError, ValueError):
            week = None
    if not any((ids, classes, majors, week is not None)):
        return None
    out: dict[str, Any] = {
        "classes": classes or None,
        "majors": majors or None,
        "week_range": week,
        "selected_student_count": len(ids),
        "selected_student_ids": None,
        "selected_student_ids_preview": ids[:5] if ids else [],
        "selected_student_ids_truncated": len(ids) > 5,
        "scope_binding": "composer_chip",
    }
    return out


def _format_attachment_extra_lines(ui_scope: dict[str, Any] | None) -> list[str]:
    if not isinstance(ui_scope, dict):
        return []
    parts: list[str] = []
    knowledges = _clean_str_list(ui_scope.get("knowledge_ids"))
    if knowledges:
        shown = "、".join(knowledges[:8])
        more = f" 等{len(knowledges)}个" if len(knowledges) > 8 else ""
        parts.append(f"知识点: {shown}{more}")
    titles = _clean_str_list(ui_scope.get("title_ids"))
    if titles:
        shown = ", ".join(titles[:6])
        more = f" …共{len(titles)}" if len(titles) > 6 else ""
        parts.append(f"题目 title_ids: {shown}{more}")
    dataset = ui_scope.get("dataset")
    if isinstance(dataset, dict):
        ds_bits = []
        if dataset.get("dataset_id"):
            ds_bits.append(f"dataset_id={dataset['dataset_id']}")
        if dataset.get("run_id"):
            ds_bits.append(f"run_id={dataset['run_id']}")
        if dataset.get("label"):
            ds_bits.append(str(dataset["label"]))
        if ds_bits:
            parts.append("基于查询结果: " + "; ".join(ds_bits))
    view = ui_scope.get("view_snapshot")
    if isinstance(view, dict) and view.get("view"):
        params = view.get("params") if isinstance(view.get("params"), dict) else {}
        parts.append(f"视图快照: {view['view']} params={params}")
    report = ui_scope.get("report")
    if isinstance(report, dict) and report.get("path"):
        label = report.get("label") or report["path"]
        parts.append(f"继续编辑报告: {label} ({report['path']})")
    return parts


def format_ui_scope_agent_hint(ui_scope: dict[str, Any] | None) -> str | None:
    """Backward-compatible extras-only hint (prefer ``format_turn_scope_hint``)."""
    return format_turn_scope_hint(ui_scope=ui_scope, filter_context=None)


def compose_llm_user_content(teacher_text: str, turn_scope_hint: str | None) -> str:
    """
    Single user message for the LLM: optional turn-scope prefix + teacher text.

    Keeps OpenAI-style role alternation (one user turn) and leaves prior history
    untouched so prompt-prefix cache can still hit.
    Teacher UI must use ``clean_user_content_for_display`` / ``ui_messages``.
    """
    text = (teacher_text or "").strip()
    hint = (turn_scope_hint or "").strip()
    if not hint:
        return text
    if not text:
        return hint
    return f"{hint}\n\n---\n教师本轮问题：\n{text}"


def format_turn_scope_hint(
    *,
    ui_scope: dict[str, Any] | None = None,
    filter_context: FilterContext | None = None,
) -> str | None:
    """
    Per-turn scope for the LLM (ui-hidden user message).

    Keeps the system prompt stable for prefix cache and avoids rewriting
    "current Nav scope" over earlier turns in the same conversation.
    """
    blocks: list[str] = []

    nav = _nav_summary_from_ui_scope(ui_scope)
    if nav is None and filter_context is not None:
        nav = filter_context.to_summary_dict()
    if nav is not None:
        has_nav = bool(
            nav.get("classes")
            or nav.get("majors")
            or nav.get("week_range")
            or (nav.get("selected_student_count") or 0) > 0
            or nav.get("typical_student_ids")
        )
        if has_nav:
            blocks.append(format_filter_context_section(nav))

    extras = _format_attachment_extra_lines(ui_scope)
    if extras:
        blocks.append("--- 本轮附加附件 ---\n" + "\n".join(f"- {line}" for line in extras))

    if not blocks:
        return None

    preamble = (
        "[系统·本轮范围] 以下仅适用于**本轮**教师问题；更早轮次的范围可能不同，"
        "请勿把本范围套用到历史结论。"
        "勿向教师复述本段。"
        "结构化查询仍默认绑定会话 filter_context；"
        "需完整学号时调用 get_current_filter_context(include_student_ids=true)。\n\n"
    )
    return preamble + "\n\n".join(blocks)


def build_ui_scope_payload(context: dict[str, Any] | None) -> dict[str, Any] | None:
    """Normalize optional ui_scope from message context for the durable transcript.

    Accepts any non-empty combination of students / classes / majors / week_range
    and composer extras (knowledge, dataset, view, report).
    """
    if not isinstance(context, dict):
        return None
    raw = context.get("ui_scope")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return None
    out: dict[str, Any] = {}
    ids = _clean_str_list(raw.get("selected_student_ids"))
    if ids:
        out["selected_student_ids"] = ids
    classes = _clean_str_list(raw.get("classes"))
    if classes:
        out["classes"] = classes
    majors = _clean_str_list(raw.get("majors"))
    if majors:
        out["majors"] = majors
    wr = raw.get("week_range")
    if isinstance(wr, (list, tuple)) and len(wr) >= 2:
        try:
            out["week_range"] = [int(wr[0]), int(wr[1])]
        except (TypeError, ValueError):
            pass
    knowledges = _clean_str_list(raw.get("knowledge_ids"))
    if knowledges:
        out["knowledge_ids"] = knowledges
    titles = _clean_str_list(raw.get("title_ids"))
    if titles:
        out["title_ids"] = titles
    dataset = raw.get("dataset")
    if isinstance(dataset, dict):
        ds: dict[str, Any] = {}
        run_id = str(dataset.get("run_id") or "").strip()
        dataset_id = str(dataset.get("dataset_id") or "").strip()
        if run_id:
            ds["run_id"] = run_id
        if dataset_id:
            ds["dataset_id"] = dataset_id
        label = str(dataset.get("label") or "").strip()
        if label:
            ds["label"] = label
        tool = str(dataset.get("tool") or "").strip()
        if tool:
            ds["tool"] = tool
        resource = str(dataset.get("resource") or "").strip()
        if resource:
            ds["resource"] = resource
        if ds:
            out["dataset"] = ds
    view = raw.get("view_snapshot")
    if isinstance(view, dict) and str(view.get("view") or "").strip():
        snap: dict[str, Any] = {"view": str(view["view"]).strip()}
        params = view.get("params")
        if isinstance(params, dict):
            snap["params"] = dict(params)
        label = str(view.get("label") or "").strip()
        if label:
            snap["label"] = label
        out["view_snapshot"] = snap
    report = raw.get("report")
    if isinstance(report, dict):
        path = str(report.get("path") or "").strip()
        if path:
            out["report"] = {
                "path": path,
                "label": str(report.get("label") or "").strip() or path.split("/")[-1],
            }
    return out or None
