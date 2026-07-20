"""Augment user turns with UI-synced analysis scope (scatter selection, nav filters)."""

from __future__ import annotations

import re
from typing import Any

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


def build_ui_scope_payload(context: dict[str, Any] | None) -> dict[str, Any] | None:
    """Normalize optional ui_scope from message context for the durable transcript.

    Accepts any non-empty combination of students / classes / majors / week_range
    so composer chips (week or class only) can persist without a student selection.
    """
    if not isinstance(context, dict):
        return None
    raw = context.get("ui_scope")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return None
    out: dict[str, Any] = {}
    ids = [str(x).strip() for x in (raw.get("selected_student_ids") or []) if str(x).strip()]
    if ids:
        out["selected_student_ids"] = ids
    classes = [str(x).strip() for x in (raw.get("classes") or []) if str(x).strip()]
    if classes:
        out["classes"] = classes
    majors = [str(x).strip() for x in (raw.get("majors") or []) if str(x).strip()]
    if majors:
        out["majors"] = majors
    wr = raw.get("week_range")
    if isinstance(wr, (list, tuple)) and len(wr) >= 2:
        try:
            out["week_range"] = [int(wr[0]), int(wr[1])]
        except (TypeError, ValueError):
            pass
    return out or None

