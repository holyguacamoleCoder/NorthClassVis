"""Inject parent session context into run_subagent dispatch."""

from __future__ import annotations

from typing import Any

from loop_state import AnalysisToolContext
from subagent import SubAgentParentContext


def inject_subagent_dispatch_args(
    tool_name: str | None,
    args: dict[str, Any],
    *,
    analysis_context: AnalysisToolContext | None = None,
    permission: Any | None = None,
    hooks: Any | None = None,
    llm_router: Any | None = None,
    filter_context: Any | None = None,
    loaded_skills: set[str] | None = None,
    loaded_references: set[str] | None = None,
    on_tool_event: Any | None = None,
    run_registry: Any | None = None,
    job_id: str | None = None,
    parent_mode: str = "analyze",
) -> dict[str, Any]:
    if tool_name != "run_subagent":
        return args
    parent_mode = (parent_mode or "analyze").strip().lower()
    parent = SubAgentParentContext(
        session_id=analysis_context.session_id if analysis_context else None,
        user_turn=analysis_context.user_turn if analysis_context else 0,
        parent_mode=parent_mode,
        filter_context=filter_context,
        visual_links=(
            list(analysis_context.session_visual_links)
            if analysis_context
            else []
        ),
        loaded_skills=set(loaded_skills or []),
        loaded_references=set(loaded_references or []),
        analysis_context=analysis_context,
    )
    return {
        **args,
        "_subagent_parent": parent,
        "_llm_router": llm_router,
        "_permission": permission,
        "_hooks": hooks,
        "_progress_callback": on_tool_event,
        "_run_registry": run_registry,
        "_job_id": job_id,
    }
