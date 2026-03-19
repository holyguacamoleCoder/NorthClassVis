# Agent 模块测试

本目录按**子模块**组织单测，并包含**模块全过程集成测试**。这里的“集成”不是把所有模块糊成一条链，而是分别验证 `intent`、`plan`、`execution` 各自公开流程是否完整走通。

## 目录结构

```text
agent/test/
  conftest.py          # 将 backend 加入 sys.path，对所有子目录生效
  intent/              # 意图/目标解析（单元测试）
    test_schemas.py
    test_goal_parser.py
    test_validator.py
    test_clarifier.py
  plan/                # 规划（任务图）（单元测试）
    test_schemas.py
    test_task_graph.py
    test_planner.py
    test_validators.py
  execution/           # 执行编译（PlanStep 展平、结果规范化）（单元测试）
    test_compiler.py
    test_result_normalizer.py
  integration/         # 模块全过程集成测试（plan + execution 等）
    __init__.py
    test_intent_module_integration.py # intent 全过程：parse_goal -> validate -> clarifier
    test_plan_module_integration.py   # plan 全过程：build_task_graph -> validate -> schedule -> compile
  # 后续可增：tools/, normalizers/, ...
```

## 运行方式

在 **backend** 目录下执行。

### 全部 / 按模块

```bash
# 跑全部 agent 测试（单元 + 集成）
pytest agent/test/ -v

# 按模块：只跑 execution / plan / intent / integration
pytest agent/test/execution/ -v
pytest agent/test/plan/ -v
pytest agent/test/intent/ -v
pytest agent/test/integration/ -v
```

### 按单文件（例如只跑 test_goal_parser）

```bash
# 指定一个测试文件
pytest agent/test/intent/test_goal_parser.py -v
pytest agent/test/execution/test_compiler.py -v
pytest agent/test/integration/test_intent_module_integration.py -v
pytest agent/test/integration/test_plan_module_integration.py -v
```

### 按单用例（指定文件 + 用例名）

```bash
# 文件::用例名
pytest agent/test/intent/test_goal_parser.py::test_parse_goal_rules_trend -v
pytest agent/test/intent/test_goal_parser.py::test_parse_goal_rules_knowledge -v
```

### 按 marker（execution / plan / intent / integration / llm）

```bash
# 从 agent/test 收集后按标记过滤
pytest agent/test/ -v -m execution
pytest agent/test/ -v -m plan
pytest agent/test/ -v -m intent
pytest agent/test/ -v -m integration

# 不跑覆盖 LLM 分支的用例
pytest agent/test/ -v -m "not llm"

# 只跑 LLM 分支（当前默认用 fake LLM client，不依赖外网）
pytest agent/test/ -v -m llm
```

`llm` marker 现在表示“覆盖 LLM 分支代码路径”，默认通过 fake client 驱动 `parse_goal()` 的 LLM 分支，不依赖真实网关。`conftest.py` 仍会尝试加载 `backend/.env`，但当前这些测试不再因为未配置 `OPENAI_API_KEY` 而被动跳过。

## 当前用例（按文件跑时可对照下表选路径）

### intent

- `intent/test_schemas.py`：`intent/schemas.py`，覆盖 `GoalSpec`
- `intent/test_goal_parser.py`：`intent/goal_parser.py`，覆盖规则兜底路径
- `intent/test_validator.py`：`intent/validator.py`，覆盖 `validate`
- `intent/test_clarifier.py`：`intent/clarifier.py`，覆盖追问逻辑
- `intent/test_goal_parser_llm.py`：`intent/goal_parser.py`，覆盖 LLM 分支单测（fake LLM，覆盖 `_parse_goal_with_llm`）

### plan

- `plan/test_schemas.py`：`plan/schemas.py`，覆盖 `SubTask`、`TaskGraph`
- `plan/test_task_graph.py`：`plan/task_graph.py`，覆盖环检测、拓扑排序
- `plan/test_planner.py`：`plan/planner.py`，覆盖 `build_task_graph`
- `plan/test_validators.py`：`plan/validators.py`，覆盖 `validate_task_graph`

### execution

- `execution/test_compiler.py`：`execution/compiler.py`，覆盖 `compile_plan`、`compile_execution_plan_to_steps`、scope 推导与异常任务跳过
- `execution/test_scheduler.py`：`execution/scheduler.py`，覆盖 `schedule`、批次划分
- `execution/test_schemas.py`：`execution/schemas.py`，覆盖 `ExecutionBatch`、`ExecutionPlan`
- `execution/test_result_normalizer.py`：`execution/result_normalizer.py`，覆盖字段映射、缺省值、空输入

### integration（模块全过程集成测试）

- `integration/test_intent_module_integration.py`：intent 全过程，覆盖 `parse_goal -> validate -> needs_clarification/build_clarification_question -> apply_clarification`，同时覆盖规则路径、LLM 分支路径、LLM 非法输出 fallback
- `integration/test_plan_module_integration.py`：plan+execution 全过程，覆盖 `build_task_graph -> validate_task_graph -> schedule -> compile_execution_plan_to_steps -> compile_plan -> extract_tool_results`，同时覆盖正常映射、并行批次、澄清短路、fallback

- `integration/` 目录现在只放“按模块的全过程测试”，不再放 `orchestrator` 级别的混合集成测试。
- `llm` 标记用于覆盖 LLM 分支代码路径，不代表一定会访问真实外部 LLM。

---

`conftest.py` 会将 backend 加入 `sys.path`，保证 `agent` 包可被正确导入。
