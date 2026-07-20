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
    "已加载技能会写入本会话；SKILL 全文在 load_skill 的 tool result 中（会话内 pin，不压缩）。"
)

MEMORY_COMMAND_HELP = (
    "**/memories** — 列出跨会话持久记忆（`backend/.agent/memory/`）\n"
    "Agent 在 analyze/produce 下可用 **memory** / **save_memory** 工具写入。"
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
    if head in ("/memories", "/memory"):
        return SlashCommand(kind="memories", args=parts[1:])
    return None


def list_skills_payload(registry: SkillRegistry) -> list[dict[str, str]]:
    from skills.registry import catalog_skill_names

    rows: list[dict[str, str]] = []
    for name in catalog_skill_names(registry):
        doc = registry.documents[name]
        rows.append(
            {
                "name": name,
                "description": doc.manifest.description,
            }
        )
    return rows


def _format_memories_list() -> str:
    from common.memory import get_memory_manager

    mgr = get_memory_manager()
    mgr.load_all()
    entries = mgr.list_entries()
    lines = ["**持久记忆**（跨会话）：", ""]
    if not entries:
        lines.append("_（暂无 — Agent 可在 analyze/produce 下使用 memory 工具保存）_")
    else:
        current_type = None
        for row in entries:
            if row["type"] != current_type:
                current_type = row["type"]
                lines.append(f"**[{current_type}]**")
            desc = row.get("description") or row.get("preview") or ""
            lines.append(f"- `{row['name']}` — {desc}")
    lines.extend(["", MEMORY_COMMAND_HELP])
    return "\n".join(lines)


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

    if command.kind == "memories":
        answer = _format_memories_list()
    elif command.kind == "skill":
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
                    "正文见先前 load_skill 的 tool result；可直接继续分析或写报告。"
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
                    "SKILL 全文已写入 tool result（会话内 pin）。按技能章节与工具链继续即可。"
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
    from session.display import append_ui_turn, messages_for_ui

    append_ui_turn(
        session,
        display_user_text=user_line,
        turn_messages=[
            {"role": "user", "content": user_line},
            {"role": "assistant", "content": answer},
        ],
    )
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
        "messages": serialize_messages(messages_for_ui(session)),
        "todo_items": list(session.todo_items or []),
        "filter_context": session.filter_context,
        "loaded_skills": sorted(loaded_set),
        "loaded_references": list(session.loaded_references or []),
    }
