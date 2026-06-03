"""Classify memory content: cross-session vs session-scoped (must not persist)."""

from __future__ import annotations

import re

# Mongo-style student ids used in this project (20+ hex chars).
_STUDENT_ID_RE = re.compile(r"\b[a-f0-9]{20,}\b", re.I)

_REPORT_DELIVERY_RE = re.compile(
    r"(报告.{0,8}(已生成|已完成|已写入|已输出)|学情.{0,6}报告.{0,6}(已|完成))",
    re.I,
)
_WEEK_RANGE_RE = re.compile(r"\d+\s*[~～\-至]\s*\d+\s*周|\d+\s*周.{0,12}(学情|报告|分析)", re.I)
_VIZ_GAP_RE = re.compile(
    r"(待补|需补|未完全|未完成|缺少).{0,24}(面板|视图|PortraitView|ScatterView|visual)",
    re.I,
)
_REPORTS_PATH_RE = re.compile(r"\breports/[\w./\-]+\b", re.I)
_EXPORTS_PATH_RE = re.compile(r"\bexports/[\w./\-]+\b", re.I)
_RESULT_REF_RE = re.compile(r"\bresult_ref\b", re.I)


def is_session_scoped_content(text: str) -> bool:
    """True when content belongs in session todo/deliverables, not durable memory."""
    raw = (text or "").strip()
    if not raw:
        return False
    if _REPORTS_PATH_RE.search(raw) or _EXPORTS_PATH_RE.search(raw):
        return True
    if _RESULT_REF_RE.search(raw):
        return True
    if _REPORT_DELIVERY_RE.search(raw):
        return True
    has_student = bool(_STUDENT_ID_RE.search(raw))
    has_week = bool(_WEEK_RANGE_RE.search(raw))
    has_viz_gap = bool(_VIZ_GAP_RE.search(raw))
    if has_student and (has_week or has_viz_gap or "报告" in raw):
        return True
    if has_week and has_viz_gap:
        return True
    return False


def session_scoped_memory_error(text: str) -> str | None:
    if not is_session_scoped_content(text):
        return None
    return (
        "Error: content looks like session/task state (student id, report delivery, week range, "
        "deliverable path) — not cross-session memory | "
        "Use todo_write for in-progress steps; write conclusions to reports/. "
        "Reports under reports/ are tracked in this session automatically."
    )
