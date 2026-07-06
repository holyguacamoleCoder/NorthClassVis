import os
import runtime_bootstrap  # noqa: F401  # must run before loop/tools → data → core

from loop import AgentLoop
from common.llm_router import LLMRouter
from common.memory import get_memory_manager
from common.paths import bootstrap_agent_paths
from data.filter_context import FilterContext, merge_defaults
from hooks import HookManager
from permission import CapabilityMode, CliApprovalHandler, PermissionManager
from session import SessionManager
from skills import get_registry
from slash_commands import execute_slash_command, parse_slash_command

MODE_HELP = "consult | analyze | produce"
SESSION_HELP = (
    "/new | /sessions | /session <id> | /rename <title> | /delete [id] | "
    "/context <k=v ...> | /skill [name]"
)


def _parse_mode(raw: str) -> CapabilityMode | None:
    value = raw.strip().lower()
    try:
        return CapabilityMode(value)
    except ValueError:
        return None


def _print_session_banner(session_manager: SessionManager) -> None:
    active = session_manager.active
    if not active:
        return
    print(f"[Session: {active.id} | {active.title} | {len(active.messages)} messages]")


def _handle_session_command(line: str, session_manager: SessionManager) -> bool:
    """Return True if the line was a session command (do not send to the model)."""
    stripped = line.strip()
    if not stripped.startswith("/"):
        return False

    parts = stripped.split(maxsplit=2)
    cmd = parts[0].lower()

    if cmd == "/new":
        mode = session_manager.active.permission_mode if session_manager.active else "consult"
        session = session_manager.create_session(permission_mode=mode)
        print(f"[New session: {session.id}]")
        if session.session_context:
            print("[SessionStart: data catalog injected]")
        _print_session_banner(session_manager)
        return True

    if cmd == "/sessions":
        rows = session_manager.list_sessions()
        active_id = session_manager.active.id if session_manager.active else None
        if not rows:
            print("  (no sessions)")
            return True
        for meta in rows:
            mark = "*" if meta.id == active_id else " "
            print(
                f"  {mark} {meta.id}  {meta.title}  "
                f"({meta.message_count} msgs, {meta.permission_mode})"
            )
        return True

    if cmd == "/session" and len(parts) >= 2:
        target = parts[1].strip()
        loaded = session_manager.switch_session(target)
        if loaded is None:
            print(f"Session not found: {target}")
        else:
            print(f"[Switched to {loaded.id} | {loaded.title}]")
            _print_session_banner(session_manager)
        return True

    if cmd == "/rename" and len(parts) >= 2:
        title = stripped[len("/rename"):].strip()
        if session_manager.rename_active(title):
            print(f"[Renamed to: {session_manager.active.title}]")
        else:
            print("Usage: /rename <title>")
        return True

    if cmd == "/delete":
        target = parts[1].strip() if len(parts) >= 2 else None
        if target is None:
            if not session_manager.active:
                print("No active session")
                return True
            target = session_manager.active.id
        if session_manager.delete_session(target):
            print(f"[Deleted session {target}]")
            if session_manager.active:
                _print_session_banner(session_manager)
            else:
                session_manager.create_session()
                print("[Created fresh session after delete]")
                _print_session_banner(session_manager)
        else:
            print(f"Session not found: {target}")
        return True

    return False


def _parse_context_command(line: str) -> FilterContext | None:
    """Parse /context classes=Class1 week_range=10,25 selected_student_ids=a,b"""
    stripped = line.strip()
    if not stripped.lower().startswith("/context"):
        return None
    tail = stripped[len("/context"):].strip()
    body: dict = {}
    if tail:
        for token in tail.split():
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key == "week_range":
                body["week_range"] = value
            elif key in ("classes", "majors", "selected_student_ids"):
                body[key] = [x.strip() for x in value.split(",") if x.strip()]
    fc = FilterContext.from_http_body(body) if body else None
    if fc is None:
        fc = FilterContext(source="session")
    else:
        fc = FilterContext(
            classes=fc.classes,
            majors=fc.majors,
            week_range=fc.week_range,
            selected_student_ids=fc.selected_student_ids,
            source="session",
        )
    return merge_defaults(fc)


def _bootstrap_filter_context(session_manager: SessionManager) -> None:
    env_ctx = FilterContext.from_env()
    if env_ctx is not None:
        session_manager.set_filter_context(env_ctx)
        print("[FilterContext: loaded from environment defaults]")


# Agent Loop 生命周期 (agent_service session层级)
#  权限检查 -> 技能加载 -> session加载 -> llm_client初始化 -> loop_state初始化 -> agent_loop初始化 -> agent_loop.run_loop() -> session_manager.sync_loop_state() -> session_manager.persist_active()
#  中断检查

def pipeline():
    bootstrap_agent_paths()
    
    # 权限与模式
    print(f"Capability modes: {MODE_HELP} (default: consult)")
    print(f"Session commands: {SESSION_HELP}")
    mode_input = input("Mode (consult): ").strip().lower() or "consult"
    mode = _parse_mode(mode_input) or CapabilityMode.CONSULT
    perms = PermissionManager(mode=mode, approval=CliApprovalHandler())
    print(f"[Permission mode: {mode.value}]")
    if mode == CapabilityMode.CONSULT:
        print("[Tip: 班级/成绩分析请用 /mode analyze 以启用 query_data]")

    # 加载hooks相关
    hooks = HookManager()
    if any(hooks.hooks[e] for e in hooks.hooks):
        print("[Hooks: loaded from .hooks.json]")

    # 加载memory相关
    mem_count = get_memory_manager().load_all()
    if mem_count:
        print(f"[Memories: {mem_count} loaded from .memory/]")
    else:
        print("[Memories: none yet — agent can create them with save_memory]")

    # 加载skill
    skill_registry = get_registry()
    if skill_registry.documents:
        names = ", ".join(sorted(skill_registry.documents))
        print(
            f"[Skills: {len(skill_registry.documents)} from "
            f"{skill_registry.skills_dir.name}/ ({names})]"
        )

    # 加载session
    session_manager = SessionManager(hooks=hooks, skills=skill_registry)
    session = session_manager.bootstrap(permission_mode=mode.value)
    _bootstrap_filter_context(session_manager)
    if session.session_context and not session.messages:
        print("[SessionStart: data catalog injected into agent context]")
    _print_session_banner(session_manager)

    llm_router = LLMRouter.from_env()
    models = llm_router.models_summary()
    print(
        "[LLM models: "
        f"main={models['main']}, consult={models['consult']}, "
        f"produce={models['produce']}, binding={models['binding']}, "
        f"compact={models['compact']}]"
    )

    # query_turn循环
    while True:
        try:
            query = input("请输入问题: ")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ["exit", "quit", "q"]:
            break

        if _handle_session_command(query, session_manager):
            continue

        if query.startswith("/mode"):
            parts = query.split()
            if len(parts) == 2:
                new_mode = _parse_mode(parts[1])
                if new_mode is not None:
                    perms.mode = new_mode
                    if session_manager.active:
                        session_manager.active.permission_mode = new_mode.value
                        session_manager.persist_active()
                    print(f"[Switched to {new_mode.value} mode]")
                else:
                    print(f"Unknown mode. Usage: /mode <{MODE_HELP}>")
            else:
                print(f"Usage: /mode <{MODE_HELP}>")
            continue

        if query.strip() == "/memories":
            mgr = get_memory_manager()
            if mgr.memories:
                for name, mem in mgr.memories.items():
                    print(f"  [{mem['type']}] {name}: {mem['description']}")
            else:
                print("  (no memories)")
            continue

        if query.strip() == "/rules":
            for i, rule in enumerate(perms.rules):
                print(f"  {i}: {rule}")
            continue

        if query.strip().lower().startswith("/context"):
            ctx = _parse_context_command(query)
            if ctx is not None:
                session_manager.set_filter_context(merge_defaults(ctx))
                session_manager.persist_active()
                print(f"[FilterContext: {merge_defaults(ctx).to_dict()}]")
            else:
                print("Usage: /context classes=Class1 [week_range=10,25] [selected_student_ids=id1,id2]")
            continue

        slash = parse_slash_command(query)
        if slash is not None:
            try:
                result = execute_slash_command(
                    session_manager,
                    skill_registry,
                    slash,
                    user_line=query.strip(),
                )
                print(result.get("answer") or "")
                loaded = result.get("loaded_skills") or []
                if loaded:
                    print(f"[Loaded skills: {', '.join(loaded)}]")
            except Exception as exc:
                print(f"[Skill command failed: {exc}]")
            continue

        session_manager.maybe_set_title_from_message(query)
        loop_state = session_manager.to_loop_state(perms)
        loop_state.analysis_context.session_id = loop_state.session_id
        loop_state.analysis_context.begin_user_turn(query)
        loop_state.messages.append({
            "role": "user",
            "content": query,
        })

        agent_loop = AgentLoop(
            loop_state,
            llm_router=llm_router,
            permission=perms,
            hooks=hooks,
        )
        agent_loop.run_loop()

        session_manager.sync_loop_state(loop_state)
        session_manager.persist_active()

        last = loop_state.messages[-1] if loop_state.messages else None
        if last and last.get("role") == "assistant":
            print(last.get("content") or "")

    session_manager.persist_active()


if __name__ == "__main__":
    pipeline()
