"""Augment user turns with UI-synced analysis scope (scatter selection, nav filters)."""

from __future__ import annotations

import re

from data.filter_context import FilterContext

_SELECTION_INTENT = re.compile(
    r"我选|选的|选中|这几|这批|所选|选中的|已经选择|选择了|选了|selected",
    re.IGNORECASE,
)


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
    if not _SELECTION_INTENT.search(text):
        return content

    ids = list(fc.selected_student_ids)
    preview = ", ".join(ids[:30])
    if len(ids) > 30:
        preview = f"{preview} …（共 {len(ids)} 人）"
    else:
        preview = f"{preview}（共 {len(ids)} 人）"

    return (
        f"{text}\n\n"
        "[系统·UI 同步] 教师已在可视化面板选中以下学生，请直接用于 query_data / 分析，"
        "勿再索要学号或姓名：\n"
        f"student_ID: {preview}"
    )
