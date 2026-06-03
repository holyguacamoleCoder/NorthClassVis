"""Auto-register report-writing and tier references in produce / report flows."""

from __future__ import annotations

import json
import re
from typing import Any

from skills.message_meta import attach_pin_meta
from skills.registry import SkillRegistry, _resolve_skill_name
from skills.tool_result import (
    CONTENT_KIND_REFERENCE,
    CONTENT_KIND_SKILL,
    default_skill_references_hint,
    format_reference_load_result,
    format_skill_load_result,
)
from skills.references import read_reference_text
from tools.handlers.load_skill import run_load_skill


def messages_contain_skill_pin(messages: list[dict[str, Any]], skill_name: str) -> bool:
    marker = f'✅ Skill "{skill_name}"'
    for msg in messages:
        if msg.get("role") != "tool":
            continue
        meta = msg.get("_agent_meta") or {}
        if (
            meta.get("content_kind") == CONTENT_KIND_SKILL
            and meta.get("resource_id") == skill_name
        ):
            return True
        if marker in (msg.get("content") or ""):
            return True
    return False


def append_produce_report_writing_bootstrap(
    messages: list[dict[str, Any]],
    loaded_skills: set[str],
    registry: SkillRegistry,
) -> bool:
    """
    Ensure produce mode has report-writing in loaded_skills and a pinned tool result.
    Returns True if messages were appended.
    """
    skill_name = "report-writing"
    if messages_contain_skill_pin(messages, skill_name):
        loaded_skills.add(skill_name)
        return False

    if skill_name not in registry.documents:
        loaded_skills.add(skill_name)
        return False

    if skill_name not in loaded_skills:
        run_load_skill(skill_name, _loaded_skills=loaded_skills)
    else:
        # loaded but no pin message (e.g. after macro) — rebuild body from registry
        loaded_skills.add(skill_name)

    skill_xml = registry.load_full_text(skill_name)
    content = format_skill_load_result(
        skill_name,
        skill_xml,
        references_hint=default_skill_references_hint(),
    )
    call_id = "auto-load-report-writing"
    messages.append({
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {
                    "name": "load_skill",
                    "arguments": json.dumps({"name": skill_name}, ensure_ascii=False),
                },
            }
        ],
    })
    tool_msg = attach_pin_meta(
        {"role": "tool", "tool_call_id": call_id, "content": content},
        content_kind=CONTENT_KIND_SKILL,
        resource_id=_resolve_skill_name(skill_name),
    )
    messages.append(tool_msg)
    return True


def messages_contain_reference_pin(messages: list[dict[str, Any]], ref_id: str) -> bool:
    marker = f'✅ Reference "{ref_id}"'
    for msg in messages:
        if msg.get("role") != "tool":
            continue
        meta = msg.get("_agent_meta") or {}
        if (
            meta.get("content_kind") == CONTENT_KIND_REFERENCE
            and meta.get("resource_id") == ref_id
        ):
            return True
        if marker in (msg.get("content") or ""):
            return True
    return False


_STUDENT_ID_RE = re.compile(r"[0-9a-f]{16,24}", re.I)


def infer_report_reference_tier(
    user_message: str | None,
    filter_context: Any | None = None,
) -> str | None:
    """Guess student/class/major reference tier from the current teacher request."""
    if filter_context is not None:
        ids = getattr(filter_context, "selected_student_ids", None) or []
        if len(ids) == 1:
            return "student"

    text = (user_message or "").strip()
    if not text:
        return None
    lower = text.lower()

    if any(
        k in text
        for k in ("学情报告", "诊断报告", "个体诊断", "学生报告", "给学生")
    ) or _STUDENT_ID_RE.search(text):
        return "student"
    if "reports/student" in lower or "/student/" in lower:
        return "student"
    if any(k in text for k in ("班级总览", "本班", "班级报告")) or re.search(
        r"class\s*\d+", lower
    ):
        return "class"
    if any(k in text for k in ("专业分析", "专业报告", "跨班")):
        return "major"
    return None


def append_report_reference_bootstrap(
    messages: list[dict[str, Any]],
    loaded_references: set[str],
    *,
    user_message: str | None,
    filter_context: Any | None = None,
    loaded_skills: set[str] | None = None,
) -> bool:
    """
    Pin the tier reference (student/class/major) when report-writing is active.
    Returns True if messages were appended.
    """
    if loaded_skills is not None and "report-writing" not in loaded_skills:
        return False

    tier = infer_report_reference_tier(user_message, filter_context)
    if not tier:
        return False
    if messages_contain_reference_pin(messages, tier):
        loaded_references.add(tier)
        return False

    found = read_reference_text(tier)
    if found is None:
        return False
    _rel, body = found
    loaded_references.add(tier)
    content = format_reference_load_result(tier, body)
    call_id = f"auto-load-reference-{tier}"
    messages.append(
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": "load_reference",
                        "arguments": json.dumps({"name": tier}, ensure_ascii=False),
                    },
                }
            ],
        }
    )
    tool_msg = attach_pin_meta(
        {"role": "tool", "tool_call_id": call_id, "content": content},
        content_kind=CONTENT_KIND_REFERENCE,
        resource_id=tier,
    )
    messages.append(tool_msg)
    return True
