# Intent 目标解析

用户 query 进入 Agent 后，在本模块完成**目标解析 → 校验 → 追问**，产出 **GoalSpec**。  
规划（GoalSpec → TaskGraph）在 **plan** 模块；调度与 ExecutionPlan、工具执行编排在 **execution** 模块。

---

## 执行顺序（流水线）

```text
User Query + Context
        │
        ▼
┌───────────────────┐
│  goal_parser       │  1) 解析：query → GoalSpec（LLM 主路径 / 规则兜底）
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  validator        │  2) 校验：能力范围（枚举）、非学情（可选）
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  clarifier        │  3) 追问：缺关键槽位时设置 needs_clarification + 追问文案
└─────────┬─────────┘
          │
          ▼
     GoalSpec → plan 模块（build_task_graph → schedule）→ execution 模块（compile_plan / extract_tool_results）→ tools/runner → answer_generator
```

编排层实际调用顺序：`parse_goal` → 非学情分支 → `apply_clarification` → **execution.compile_plan(goal)**。

---

## 各文件作用

| 文件               | 作用                                                                                                                                          |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------- |
| **schemas.py**     | 定义 **GoalSpec**：结构化目标（subject/mode/scope、输出要求、约束条件、状态）。                                                               |
| **goal_parser.py** | **目标解析**。`parse_goal(question, context)`：LLM 主路径 / 规则兜底，产出 GoalSpec。                                                         |
| **validator.py**   | **合法性校验**。`validate(goal)`：非学情、subject/mode 在合法枚举内（不依赖 plan）。                                                          |
| **clarifier.py**   | **追问**。`needs_clarification(goal)`、`build_clarification_question(goal)`、`apply_clarification(goal)`。                                    |
| ****init**.py**    | 对外暴露 `GoalSpec`、`parse_goal`、`parse_intent`、`validate`、`apply_clarification`、`needs_clarification`、`build_clarification_question`。 |

---

## 依赖关系

- **intent** 不依赖 **plan**。规划由编排层串联 `plan` 与 `execution` 完成。
- **schemas**：无其他 agent 依赖。
- **goal_parser**：依赖 schemas、context_utils、llm_client、prompts。
- **validator**：仅依赖 schemas（枚举校验，不查规划表）。
- **clarifier**：仅依赖 schemas。

---

## 测试

意图相关单测在 `agent/test/intent/` 下。从 backend 目录执行：`pytest agent/test/intent/ -v`。
