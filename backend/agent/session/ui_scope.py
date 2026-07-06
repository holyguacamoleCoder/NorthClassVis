"""Augment user turns with UI-synced analysis scope (scatter selection, nav filters)."""

from __future__ import annotations

import re

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
    When the teacher refers to UI-selected students, attach explicit student_IDs
    so the model does not ask for IDs again.
    """
    text = (content or "").strip()
    if not text or fc is None or not fc.selected_student_ids:
        return content
    if not teacher_has_selection_intent(text):
        return content

    ids = list(fc.selected_student_ids)
    n = len(ids)
    if n <= 5:
        id_line = f"student_ID: {', '.join(ids)}（共 {n} 人）"
    else:
        id_line = (
            f"Nav 已选 **{n} 人**（`query_data` 将自动应用 student_ids，勿索要学号；"
            "需完整列表 → `get_current_filter_context(include_student_ids=true)`）"
        )

    return (
        f"{text}\n\n"
        "[系统·UI 同步] 教师已在可视化面板选中学生，请直接用于 query_data / 分析：\n"
        f"{id_line}"
    )
