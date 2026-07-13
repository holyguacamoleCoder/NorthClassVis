"""Parent-agent tool: delegate an isolated sub-agent run."""

from __future__ import annotations

from typing import Any

from common.llm_router import LLMRouter
from hooks import HookManager
from permission import PermissionManager
from subagent import SubAgentParentContext, SubAgentRunner


def run_subagent(
    kind: str,
    task: str,
    *,
    _subagent_parent: SubAgentParentContext | None = None,
    _llm_router: LLMRouter | None = None,
    _permission: PermissionManager | None = None,
    _hooks: HookManager | None = None,
    _progress_callback=None,
    _run_registry: Any | None = None,
    _job_id: str | None = None,
) -> str:
    if not (task or "").strip():
        return "Error: task is required | Next: describe scope, deliverable path, and acceptance"
    if _llm_router is None:
        from common.llm_router import LLMRouter

        _llm_router = LLMRouter.from_env()

    runner = SubAgentRunner(
        llm_router=_llm_router,
        permission=_permission,
        hooks=_hooks,
        progress_callback=_progress_callback,
        run_registry=_run_registry,
        job_id=_job_id,
    )
    result = runner.run(kind, task, parent=_subagent_parent)
    return result.format_tool_result()
