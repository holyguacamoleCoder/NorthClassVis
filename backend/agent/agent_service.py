from loop import AgentLoop, LoopState
from common.llm_client import LLMClient
from hooks import HookManager
from permission import CapabilityMode, CliApprovalHandler, PermissionManager
from skills import get_registry

MODE_HELP = "consult | analyze | produce"


def _parse_mode(raw: str) -> CapabilityMode | None:
    value = raw.strip().lower()
    try:
        return CapabilityMode(value)
    except ValueError:
        return None


def pipeline():
    print(f"Capability modes: {MODE_HELP} (default: consult)")
    mode_input = input("Mode (consult): ").strip().lower() or "consult"
    mode = _parse_mode(mode_input) or CapabilityMode.CONSULT
    perms = PermissionManager(mode=mode, approval=CliApprovalHandler())
    print(f"[Permission mode: {mode.value}]")

    hooks = HookManager()
    if any(hooks.hooks[e] for e in hooks.hooks):
        print("[Hooks: loaded from .hooks.json]")
    session_result = hooks.run_hooks(
        "SessionStart",
        {"tool_name": "", "tool_input": {}},
    )
    session_context: list[str] = list(session_result.messages)
    if session_context:
        print("[SessionStart: data catalog injected into agent context]")

    skill_registry = get_registry()
    if skill_registry.documents:
        names = ", ".join(sorted(skill_registry.documents))
        print(f"[Skills: {len(skill_registry.documents)} from {skill_registry.skills_dir.name}/ ({names})]")

    loop_state = LoopState(
        messages=[],
        permission=perms,
        hooks=hooks,
        session_context=session_context,
        skills=skill_registry,
    )
    llm_client = LLMClient()

    while True:
        try:
            query = input("请输入问题: ")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ["exit", "quit", "q"]:
            break
        
        # 处理/mode命令
        if query.startswith("/mode"):
            parts = query.split()
            if len(parts) == 2:
                new_mode = _parse_mode(parts[1])
                if new_mode is not None:
                    perms.mode = new_mode
                    loop_state.permission = perms
                    print(f"[Switched to {new_mode.value} mode]")
                else:
                    print(f"Unknown mode. Usage: /mode <{MODE_HELP}>")
            else:
                print(f"Usage: /mode <{MODE_HELP}>")
            continue
        
        # 处理/rules命令
        if query.strip() == "/rules":
            for i, rule in enumerate(perms.rules):
                print(f"  {i}: {rule}")
            continue

        loop_state.messages.append({
            "role": "user",
            "content": query,
        })

        agent_loop = AgentLoop(
            loop_state,
            llm_client=llm_client,
            permission=perms,
            hooks=hooks,
        )
        agent_loop.run_loop()

        last = loop_state.messages[-1] if loop_state.messages else None
        if last and last.get("role") == "assistant":
            print(last.get("content") or "")


if __name__ == "__main__":
    pipeline()
