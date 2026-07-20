"""Format load_skill / load_reference tool results (full body in tool message)."""

from __future__ import annotations

COMPACT_POLICY_PIN = "pin"
CONTENT_KIND_SKILL = "skill_load"
CONTENT_KIND_REFERENCE = "reference_load"
CONTENT_KIND_COMPACT_SUMMARY = "compact_summary"
CONTENT_KIND_OUTPUT_CONTINUATION = "output_continuation"
CONTENT_KIND_UI_SCOPE_HINT = "ui_scope_hint"


def format_skill_load_result(
    name: str,
    skill_xml: str,
    *,
    references_hint: str | None = None,
) -> str:
    """Full skill body for first load_skill in a session."""
    lines = [
        f'✅ Skill "{name}" 已加载',
        "",
        "以下是 SKILL.md 的完整内容",
        "",
        skill_xml.strip(),
    ]
    if references_hint:
        lines.extend(["", references_hint])
    return "\n".join(lines)


def format_skill_active_result(name: str) -> str:
    return (
        f'[Skill active: {name}] 完整说明已在本会话先前的 load_skill tool result 中；'
        "勿重复 load。继续 query_data / aggregate_data，或 load 其他技能。"
    )


def format_reference_load_result(ref_id: str, body: str) -> str:
    lines = [
        f'✅ Reference "{ref_id}" 已加载',
        "",
        "以下是参考文档的完整内容",
        "",
        body.strip(),
    ]
    return "\n".join(lines)


def format_reference_active_result(ref_id: str) -> str:
    return (
        f'[Reference active: {ref_id}] 完整说明已在本会话先前的 load_reference tool result 中；'
        "勿重复 load。"
    )


def is_fresh_skill_load(content: str) -> bool:
    return content.strip().startswith('✅ Skill "') or "<skill " in content


def is_fresh_reference_load(content: str) -> bool:
    return content.strip().startswith('✅ Reference "')


def default_skill_references_hint() -> str:
    return (
        "## 参考（写标准报告前必做）\n"
        "按粒度 **load_reference**：student / class / major / freeform。"
        "个体学情须先 load_reference(\"student\")，再写 reports/student/…。"
    )
