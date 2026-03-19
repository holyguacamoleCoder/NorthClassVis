# Plan 规划模块

校验通过后的**目标**在本模块被拆解为**任务依赖图**。  
本模块只负责“规划”，不负责执行调度与工具执行编排（`schedule`、`PlanStep` 编译与工具结果规范化都在 `execution` 模块）。

---

## 执行顺序（流水线）

```text
GoalSpec（来自 intent）
        │
        ▼
┌───────────────────┐
│  planner          │  1) 选择策略，生成任务图 build_task_graph(goal) → TaskGraph
└─────────┬─────────┘
          │
          ▼
```

编排层通常调用顺序：`plan.build_task_graph(goal)`，然后把 `TaskGraph` 交给 `execution` 模块完成 `schedule`、执行编译与工具调用。

---

## 各文件作用

- `schemas.py`：`SubTask`、`TaskGraph`。子任务含输入输出、所需工具、依赖、优先级。`ExecutionBatch`、`ExecutionPlan` 已迁至 `execution/schemas.py`。
- `task_graph.py`：图操作，含环检测 `has_cycle`、拓扑排序 `topological_sort`（供 validators 等使用）；并行批次划分在 `execution/scheduler`。
- `strategies.py`：规划策略。`INTENT_PLAN_MAP`（subject×mode→工具）在此；`SimpleRuleStrategy` 将 GoalSpec 查表展开为无依赖子任务；可扩展 ToT。
- `planner.py`：规划入口，提供 `build_task_graph(goal)`、`select_strategy(goal)`。
- `validators.py`：规划层校验，提供 `validate_task_graph`（环、任务必有工具等）。

---

## 依赖关系

- **intent**：不依赖 plan。goal 由 intent 产出后传入 plan。
- **plan** 依赖 **intent**：仅依赖 `GoalSpec`（strategies/planner 用）；不依赖 intent 的解析/追问逻辑。
- **plan** 不直接依赖执行层契约（`PlanStep`、`ToolResult`）。

---

## 测试

规划相关单测在 `agent/test/plan/` 下。从 backend 目录执行：`pytest agent/test/plan/ -v`。
