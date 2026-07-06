"""One-shot smoke test: run a real analyze query and log per-call-site models."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGENT_DIR))
import runtime_bootstrap  # noqa: F401  # after path bootstrap

from common.llm_client import LLMClient
from common.llm_router import LLMRouter
from common.paths import bootstrap_agent_paths
from hooks import HookManager
from loop import AgentLoop
from permission import CapabilityMode, DenyAskApprovalHandler, PermissionManager
from session import SessionManager
from skills import get_registry

QUERY = "Class1 有多少名不同的学生？请用 query_data 和 aggregate_data 统计后回答。"


def _patch_model_logging() -> Counter:
    calls: Counter = Counter()
    original = LLMClient.create_completion

    def _logged_create(self, *args, **kwargs):
        model = kwargs.get("model") or self.config.model
        langfuse_name = kwargs.get("langfuse_name") or (
            "main_loop" if kwargs.get("tools") else "llm_text"
        )
        calls[f"{langfuse_name}:{model}"] += 1
        print(f"  [LLM call] {langfuse_name} -> {model}", flush=True)
        return original(self, *args, **kwargs)

    LLMClient.create_completion = _logged_create  # type: ignore[method-assign]
    return calls


def main() -> int:
    bootstrap_agent_paths()
    router = LLMRouter.from_env()
    print("[Router config]", json.dumps(router.models_summary(), ensure_ascii=False))

    hooks = HookManager()
    skills = get_registry()
    manager = SessionManager(hooks=hooks, skills=skills)
    session = manager.create_session(permission_mode="analyze")
    print(f"[Session] fresh {session.id}")
    perms = PermissionManager(mode=CapabilityMode.ANALYZE, approval=DenyAskApprovalHandler())

    loop_state = manager.to_loop_state(perms)
    loop_state.analysis_context.session_id = loop_state.session_id
    loop_state.analysis_context.begin_user_turn(QUERY)
    loop_state.messages.append({"role": "user", "content": QUERY})

    print(f"\n[Query] {QUERY}\n")
    calls = _patch_model_logging()
    agent = AgentLoop(loop_state, llm_router=router, permission=perms, hooks=hooks)
    print(f"[Active main model for analyze] {agent._active_main_client().config.model}\n")
    agent.run_loop()
    manager.sync_loop_state(loop_state)

    last = loop_state.messages[-1] if loop_state.messages else None
    answer = (last or {}).get("content") or "(no assistant text)"
    print("\n[Answer preview]")
    print(answer[:1200] + ("..." if len(answer) > 1200 else ""))
    print("\n[Model call summary]")
    for key, count in sorted(calls.items()):
        print(f"  {key} x{count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
