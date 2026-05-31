"""Chat slash commands (/skill, …) — no LLM turn."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from tools.handlers.load_skill import run_load_skill

if TYPE_CHECKING:
    from session.manager import SessionManager
    from skills import SkillRegistry

SKILL_COMMAND_HELP = (
    "**/skill** — 列出可用技能\n"
    "**/skill `name`** — 加载技能（如 `analysis-class`、`data-exploration`）\n"
    "已加载技能会写入本会话，并在后续每轮 system prompt 的「已加载技能」区注入全文。"
)


@dataclass(frozen=True)
class SlashCommand:
    kind: str
    args: list[str]


def parse_slash_command(text: str) -> SlashCommand | None:
    """Return parsed command if *text* is a supported slash command."""
    stripped = (text or "").strip()
    if not stripped.startswith("/"):
        return None
    parts = stripped.split()
    head = parts[0].lower()
    if head in ("/skill", "/skills"):
        return SlashCommand(kind="skill", args=parts[1:])
    return None


def list_skills_payload(registry: SkillRegistry) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for name in sorted(registry.documents):
        doc = registry.documents[name]
        rows.append(
            {
                "name": name,
                "description": doc.manifest.description,
            }
        )
    return rows


def _format_skill_list(registry: SkillRegistry, loaded: list[str]) -> str:
    lines = ["**可用技能**（`load_skill` / `/skill <name>`）：", ""]
    for row in list_skills_payload(registry):
        mark = " ✓" if row["name"] in loaded else ""
        lines.append(f"- `{row['name']}`{mark} — {row['description']}")
    if loaded:
        lines.extend(["", f"**本会话已加载**：{', '.join(f'`{n}`' for n in loaded)}"])
    lines.extend(["", SKILL_COMMAND_HELP])
    return "\n".join(lines)


def execute_slash_command(
    session_manager: SessionManager,
    registry: SkillRegistry,
    command: SlashCommand,
    *,
    user_line: str,
) -> dict[str, Any]:
    """Run slash command, persist session messages, return HTTP turn payload."""
    from .http.adapter import build_tool_step, serialize_messages

    session = session_manager.active
    if session is None:
        raise ValueError("no active session")

    user_line = (user_line or "").strip()
    loaded_set = set(session.loaded_skills or [])
    trace_steps: list[dict[str, Any]] = []

    if command.kind == "skill":
        if not command.args or command.args[0].lower() in (
            "list",
            "ls",
            "help",
            "?",
            "h",
        ):
            answer = _format_skill_list(registry, sorted(loaded_set))
        else:
            skill_name = command.args[0].strip()
            tool_text = run_load_skill(skill_name, _loaded_skills=loaded_set)
            session.loaded_skills = sorted(loaded_set)
            if tool_text.startswith("Error:"):
                answer = tool_text
                trace_steps.append(
                    build_tool_step(
                        "load_skill",
                        {"name": skill_name},
                        tool_text,
                    )
                )
            elif "[Skill active:" in tool_text:
                answer = (
                    f"技能 `{skill_name}` 已在本会话加载。\n\n"
                    "正文见 system prompt「已加载技能」区；可直接继续分析或写报告。"
                )
                trace_steps.append(
                    build_tool_step(
                        "load_skill",
                        {"name": skill_name},
                        tool_text,
                    )
                )
            else:
                answer = (
                    f"已加载技能 **`{skill_name}`**。\n\n"
                    "流程已固定到 system prompt「已加载技能」区（每轮保留）。"
                    "按技能章节与工具链继续即可。"
                )
                trace_steps.append(
                    build_tool_step(
                        "load_skill",
                        {"name": skill_name},
                        tool_text,
                    )
                )
    else:
        answer = f"未知命令类型：{command.kind}"

    session.messages.append({"role": "user", "content": user_line})
    session.messages.append({"role": "assistant", "content": answer})
    session.updated_at = time.time()
    session_manager.persist_active()

    return {
        "answer": answer,
        "evidence": [],
        "actions": [],
        "visual_links": [],
        "trace": {"steps": trace_steps},
        "goal_check": {"is_satisfied": True, "can_stop_early": True, "reason": ""},
        "summary": None,
        "session_id": session.id,
        "session_title": session.title,
        "permission_mode": session.permission_mode,
        "messages": serialize_messages(session.messages),
        "todo_items": list(session.todo_items or []),
        "filter_context": session.filter_context,
        "loaded_skills": sorted(loaded_set),
    }
