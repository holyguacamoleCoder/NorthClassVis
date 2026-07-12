"""Cross-section consistency review for report deliverables (revision pass)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loop_state import AnalysisToolContext

from .charts import extract_chart_blocks
from .parse import infer_tier_from_path, parse_report_markdown
from .sections import section_excerpt
from .validate import validate_report

_TREND_UP = ("上升", "提高", "改善", "好转", "递增", "走高", "回升", "升至", "升高")
_TREND_DOWN = ("下降", "降低", "恶化", "递减", "走低", "变差", "下滑", "降至", "降低")
_PLACEHOLDER_RE = re.compile(
    r"(学生\s*ID|<student[_-]?id>|待补充|待写|占位符?|\bTODO\b|\bTBD\b)",
    re.I,
)
_QUESTION_ID_RE = re.compile(r"Question_[A-Za-z0-9]+")
_STUDENT_HEX_RE = re.compile(r"\b[0-9a-f]{16,24}\b", re.I)
_STUDENT_CODE_RE = re.compile(r"\b[A-Z][A-Za-z0-9]{4,}\b")


@dataclass
class ReviewIssue:
    section: str | None
    severity: str  # error | warn | info
    issue: str
    fix: str
    excerpt: str | None = None


@dataclass
class ReportReview:
    path: str
    tier: str
    status: str  # ok | needs_revision
    issues: list[ReviewIssue] = field(default_factory=list)
    validation: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "tier": self.tier,
            "status": self.status,
            "issues": [
                {
                    "section": i.section,
                    "severity": i.severity,
                    "issue": i.issue,
                    "fix": i.fix,
                    **({"excerpt": i.excerpt} if i.excerpt else {}),
                }
                for i in self.issues
            ],
            "validation": self.validation,
        }


def _trend_polarity(text: str) -> set[str]:
    found: set[str] = set()
    for token in _TREND_UP:
        if token in text:
            found.add("up")
            break
    for token in _TREND_DOWN:
        if token in text:
            found.add("down")
            break
    if "up" in found and "down" in found:
        return {"mixed"}
    return found


def _ids_from_scope(scope_body: str) -> set[str]:
    text = scope_body or ""
    ids: set[str] = set()
    for match in _STUDENT_HEX_RE.finditer(text):
        ids.add(match.group(0))
    for match in _STUDENT_CODE_RE.finditer(text):
        token = match.group(0)
        if token.lower() in ("class", "week", "view", "peak"):
            continue
        ids.add(token)
    return ids


def _weekview_student_ids(source: str) -> set[str]:
    ids: set[str] = set()
    for block in extract_chart_blocks(source):
        if (block.view or "").strip() != "WeekView":
            continue
        params = block.params or {}
        raw = params.get("student_ids")
        if isinstance(raw, list):
            for item in raw:
                if item:
                    ids.add(str(item).strip())
    return ids


def _collect_placeholders(section_id: str, body: str, path: str) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    for match in _PLACEHOLDER_RE.finditer(body or ""):
        issues.append(
            ReviewIssue(
                section=section_id,
                severity="error",
                issue=f"占位文本 {match.group(0)!r} 尚未替换",
                fix=(
                    f'edit_file path="{path}" old_text="## {section_id}" '
                    f'new_text="## {section_id}\\n<完整正文>"'
                ),
                excerpt=section_excerpt(f"## {section_id}\n{body}", f"## {section_id}"),
            )
        )
        break
    return issues


def _check_summary_week_trend(
    summary_body: str,
    week_body: str,
    path: str,
) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    s_pol = _trend_polarity(summary_body)
    w_pol = _trend_polarity(week_body)
    if not s_pol or not w_pol or "mixed" in s_pol or "mixed" in w_pol:
        return issues
    if s_pol != w_pol:
        s_word = "上升" if "up" in s_pol else "下降"
        w_word = "上升" if "up" in w_pol else "下降"
        issues.append(
            ReviewIssue(
                section="summary",
                severity="warn",
                issue=(
                    f"summary 趋势表述（{s_word}）与 week_trend（{w_word}）不一致，"
                    "通读修订时应二选一对齐"
                ),
                fix=(
                    f'edit_file path="{path}" old_text="## summary" '
                    'new_text="## summary\\n<与 week_trend 一致的结论>"'
                ),
            )
        )
    return issues


def _check_scope_weekview(
    scope_body: str,
    source: str,
    path: str,
    tier: str,
) -> list[ReviewIssue]:
    if tier != "student":
        return []
    scope_ids = _ids_from_scope(scope_body)
    chart_ids = _weekview_student_ids(source)
    if not scope_ids or not chart_ids:
        return []
    if scope_ids.isdisjoint(chart_ids):
        issues: list[ReviewIssue] = []
        issues.append(
            ReviewIssue(
                section="scope",
                severity="error",
                issue=(
                    f"scope 学生标识 {sorted(scope_ids)!r} 与 WeekView "
                    f"student_ids {sorted(chart_ids)!r} 不一致"
                ),
                fix=(
                    f'edit_file path="{path}" old_text="## week_trend" '
                    'new_text="## week_trend\\n<params.student_ids 与 scope 一致>"'
                ),
            )
        )
        return issues
    return []


def _check_actions_questions(
    actions_body: str,
    anchors_body: str,
    path: str,
) -> list[ReviewIssue]:
    action_qs = set(_QUESTION_ID_RE.findall(actions_body or ""))
    anchor_qs = set(_QUESTION_ID_RE.findall(anchors_body or ""))
    orphan = action_qs - anchor_qs
    if not orphan:
        return []
    return [
        ReviewIssue(
            section="actions",
            severity="warn",
            issue=(
                f"actions 引用了 question_anchors 未列出的题目: {sorted(orphan)!r}"
            ),
            fix=(
                f'edit_file path="{path}" old_text="## question_anchors" '
                'new_text="## question_anchors\\n<补全表格>" '
                "或修正 actions 中的题目 ID"
            ),
        )
    ]


def _check_thin_sections(
    parsed: Any,
    path: str,
    *,
    min_body_lines: int = 2,
) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    for section in parsed.sections:
        if section.id in ("evidence", "limitations"):
            continue
        if section.line_count >= min_body_lines:
            continue
        issues.append(
            ReviewIssue(
                section=section.id,
                severity="warn",
                issue=f"章节 {section.id} 仅 {section.line_count} 行，可能仍是骨架",
                fix=(
                    f'edit_file path="{path}" old_text="## {section.id}" '
                    f'new_text="## {section.id}\\n<充实正文>"'
                ),
                excerpt=section_excerpt(
                    f"## {section.id}\n{section.body}",
                    f"## {section.id}",
                ),
            )
        )
    return issues


def review_report(
    source: str,
    *,
    path: str | Path | None = None,
    tier: str | None = None,
    analysis_context: AnalysisToolContext | None = None,
    validation_level: str = "deliver",
) -> ReportReview:
    """Read full markdown and return cross-section issues plus deliver validation."""
    rel = str(path or "").strip().replace("\\", "/")
    resolved_tier = (tier or "").strip().lower()
    if not resolved_tier and rel:
        resolved_tier = infer_tier_from_path(rel)
    if not resolved_tier:
        resolved_tier = "freeform"

    parsed = parse_report_markdown(source)
    section_map = parsed.section_map()
    issues: list[ReviewIssue] = []

    for sid, section in section_map.items():
        issues.extend(_collect_placeholders(sid, section.body, rel))

    summary = section_map.get("summary")
    week_trend = section_map.get("week_trend")
    if summary and week_trend:
        issues.extend(
            _check_summary_week_trend(summary.body, week_trend.body, rel)
        )

    scope = section_map.get("scope")
    if scope:
        issues.extend(_check_scope_weekview(scope.body, source, rel, resolved_tier))

    actions = section_map.get("actions")
    anchors = section_map.get("question_anchors")
    if actions and anchors:
        issues.extend(
            _check_actions_questions(actions.body, anchors.body, rel)
        )

    issues.extend(_check_thin_sections(parsed, rel))

    validation = validate_report(
        source,
        tier=resolved_tier,
        path=rel or None,
        analysis_context=analysis_context,
        validation_level=validation_level,
    )

    for err in validation.get("errors") or []:
        issues.append(
            ReviewIssue(
                section=None,
                severity="error",
                issue=str(err),
                fix="按 [Report validate] 提示用 edit_file ## <section> 整节修复",
            )
        )

    for warn in validation.get("warnings") or []:
        text = str(warn)
        if "out of recommended order" in text:
            issues.append(
                ReviewIssue(
                    section=None,
                    severity="info",
                    issue=text,
                    fix="可选：按 tier reference 顺序重排章节",
                )
            )
            continue
        if "missing sections" in text or "empty" in text:
            issues.append(
                ReviewIssue(
                    section=None,
                    severity="warn",
                    issue=text,
                    fix='edit_file old_text 首行用 "## <section>" 填充缺失或空节',
                )
            )

    has_blocking = any(i.severity == "error" for i in issues) or not validation.get(
        "ok"
    )
    status = "needs_revision" if has_blocking or issues else "ok"
    if not issues and validation.get("ok"):
        status = "ok"

    return ReportReview(
        path=rel,
        tier=resolved_tier,
        status=status,
        issues=issues,
        validation=validation,
    )


def format_review_for_tool_result(review: ReportReview) -> str:
    """Compact tool result: issues only, not full report body."""
    lines = ["[Report review]"]
    if review.path:
        lines.append(f"path: {review.path}")
    lines.append(f"tier: {review.tier}")
    lines.append(f"status: {review.status}")

    val = review.validation or {}
    coverage = val.get("section_coverage") or {}
    if coverage.get("required"):
        lines.append(
            f"validation: level={val.get('validation_level', 'deliver')} "
            f"delivery={val.get('delivery_status', '?')} "
            f"coverage={coverage.get('present')}/{coverage.get('required')} "
            f"lines={val.get('line_count', '?')}"
        )

    cross = [i for i in review.issues if i.section]
    struct = [i for i in review.issues if not i.section]

    if cross:
        lines.append("")
        lines.append("Cross-section / per-section (fix via edit_file section_replace):")
        for idx, item in enumerate(cross[:8], start=1):
            sec = item.section or "?"
            lines.append(f"  {idx}. [{item.severity}] ## {sec}: {item.issue}")
            lines.append(f"     fix: {item.fix}")
            if item.excerpt:
                excerpt = item.excerpt.strip().replace("\n", " ")[:120]
                lines.append(f"     excerpt: {excerpt}…")

    if struct:
        lines.append("")
        lines.append("Structure / validate:")
        for idx, item in enumerate(struct[:6], start=1):
            lines.append(f"  {idx}. [{item.severity}] {item.issue}")

    remaining = len(review.issues) - 8
    if remaining > 0:
        lines.append(f"  … +{remaining} more issue(s)")

    lines.append("")
    if review.status == "ok":
        lines.append(
            "Next: 无跨节问题；确认 [Report validate: OK] 后即可向教师交付。"
        )
    else:
        lines.append(
            "Next: 用 edit_file 按 fix 逐节修订（old_text 首行 ## <id> 整节替换）；"
            "修完后再次 review_report；交付前须 [Report validate: OK]。"
        )
    return "\n".join(lines)
