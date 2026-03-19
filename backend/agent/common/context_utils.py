# 上下文规范化，供 orchestrator、intent 等共用。


def normalize_context(context):
    """将请求 context 规范为 classes / majors / selected_student_ids 列表。"""
    ctx = context or {}
    out = {
        "classes": list(ctx.get("classes") or []),
        "majors": list(ctx.get("majors") or []),
        "selected_student_ids": list(ctx.get("selected_student_ids") or []),
    }
    # 保留会话与开关字段，供编排和记忆层使用
    if "agent_llm_enabled" in ctx:
        out["agent_llm_enabled"] = bool(ctx.get("agent_llm_enabled"))
    for key in ("session_id", "conversation_id", "chat_id"):
        if key in ctx and str(ctx.get(key) or "").strip():
            out[key] = str(ctx.get(key)).strip()
    # 记忆层注入字段（存在时透传）
    if "recent_turns" in ctx:
        out["recent_turns"] = list(ctx.get("recent_turns") or [])
    if "pending_goal" in ctx and isinstance(ctx.get("pending_goal"), dict):
        out["pending_goal"] = dict(ctx.get("pending_goal"))
    if "pending_needs_clarification" in ctx:
        out["pending_needs_clarification"] = bool(ctx.get("pending_needs_clarification"))
    return out
