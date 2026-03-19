# 分步验证：Step 1 / 2e / 3（在 backend 下运行，PYTHONPATH 含 backend）
# 用法：从项目根目录 cd backend && ..\\.venv\\Scripts\\python test_steps_validation.py

import sys
import os

# 确保 backend 在路径中
if __name__ == "__main__":
    backend = os.path.dirname(os.path.abspath(__file__))
    if backend not in sys.path:
        sys.path.insert(0, backend)

def step1_contracts():
    """Step 1 — 数据契约：QuestionIntent 字段与默认值"""
    from agent.common.contracts import QuestionIntent
    intent = QuestionIntent(intent_type="overview")
    assert intent.subject == ["class"], f"subject 默认 ['class'], 实际: {intent.subject}"
    assert intent.mode == ["portrait"], f"mode 默认 ['portrait'], 实际: {intent.mode}"
    assert intent.scope == "all", f"scope 默认 'all', 实际: {intent.scope}"
    assert intent.is_out_of_domain is False, f"is_out_of_domain 默认 False, 实际: {intent.is_out_of_domain}"
    d = intent.to_dict()
    assert "subject" in d and "mode" in d and "scope" in d and "is_out_of_domain" in d
    return "Step 1 通过"

def step2e_registry():
    """Step 2e — 注册表：4 个厚工具，旧工具名不可用"""
    from agent.tools.registry import TOOL_REGISTRY, get_tool
    from agent.tools.student_tool import QueryStudentTool
    assert len(TOOL_REGISTRY) == 4, f"TOOL_REGISTRY 应有 4 个，实际: {len(TOOL_REGISTRY)}"
    assert set(TOOL_REGISTRY.keys()) == {"query_student", "query_question", "query_knowledge", "query_class"}
    t = get_tool("query_student")
    assert t is not None and type(t).__name__ == "QueryStudentTool"
    assert get_tool("get_student_portrait") is None
    return "Step 2e 通过"

def step3_compile_plan():
    """Step 3 — compile_plan：subject×mode 展开、scope 推导（execution 模块）"""
    from agent.intent.schemas import GoalSpec
    from agent.execution import compile_plan
    # (class, portrait) -> 1 步 query_class trend
    goal = GoalSpec(intent_type="overview", subject=["class"], mode=["portrait"])
    steps = compile_plan(goal)
    assert len(steps) == 1, f"预期 1 步，实际: {len(steps)}"
    assert steps[0].tool == "query_class" and steps[0].params.get("mode") == "trend"
    assert goal.scope == "all"
    # student detail -> 2 步
    goal2 = GoalSpec(intent_type="student", subject=["student"], mode=["detail"], student_ids=["s1"])
    steps2 = compile_plan(goal2)
    assert len(steps2) == 2
    assert steps2[0].params.get("mode") == "tree" and steps2[1].params.get("mode") == "detail"
    assert goal2.scope == "individual"
    # needs_clarification -> []
    goal3 = GoalSpec(intent_type="student", subject=["student"], mode=["portrait"], needs_clarification=True)
    assert len(compile_plan(goal3)) == 0
    return "Step 3 通过"

def main():
    results = []
    for name, fn in [
        ("Step 1 (contracts)", step1_contracts),
        ("Step 2e (registry)", step2e_registry),
        ("Step 3 (compile_plan)", step3_compile_plan),
    ]:
        try:
            msg = fn()
            results.append((name, "OK", msg))
        except Exception as e:
            results.append((name, "FAIL", str(e)))
    for name, status, msg in results:
        print(f"[{status}] {name}: {msg}")
    failed = [r for r in results if r[1] == "FAIL"]
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
