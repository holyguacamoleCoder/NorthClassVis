# 数据集绑定：语义意图层规划（替代「纯规则 bind」）

> **结论**：`auto` / `chain` / `fresh` 的加减分只能作**兜底与校验**，不能当作「教师意图」的主通道。  
> 当本回合存在多个 `query_data` 结果、或 aggregate 的 `input.result_ref` 与任务语义不一致时，必须引入**语义判定**（额外一轮 LLM 或等价内部逻辑），再执行 aggregate。

---

## 1. 问题重述

| 现象 | 根因 |
|------|------|
| Q1：汇总 10 条却 aggregate 全班 22960 行 | 模型显式写了全量 ref；规则在 `explicit` + 打分边界下未纠正 |
| Q2：全班概况（用户澄清：范围上可用 Class1 全量） | 绑定不是主因；资源/指标混用是另一类问题 |
| `bind` 三档 | 模型经常不传或传错；runtime 用 metrics 形状猜意图，与题干脱节 |

**教师意图**关心的是：

- 统计对象：**刚查出的 N 条 / 本班全体 / 上一题某份表 / 某 dataset_id**
- 与 **自然语言**（「这些记录」「全班」「偏科」）及 **对话阶段** 一致

这些**不能**可靠地从 `result_rows`、`count_distinct` 是否存在推导出来。

---

## 2. 设计原则

1. **语义优先、规则校验**：先定「绑哪份数据」，再用硬规则拦截明显非法（跨 turn 无 id、空 catalog、文件不存在）。
2. **只在「歧义」时花钱**：单候选、且与题干无冲突时不调用意图模型。
3. **可审计**：每次绑定留下 `binding_trace`（候选列表、resolver 输入摘要、决策、是否覆盖模型 ref）。
4. **不替代 query**：意图层只选已有 dataset，不编造数据；缺数据仍要求 `query_data`。
5. **与 Q1/Q2 区分**：链式切片 vs 全班新口径由**当前教师句**决定，不由上一题默认继承。

---

## 3. 目标架构

```
教师 user message
       │
       ▼
┌──────────────────┐     每次 query_data 登记
│  Catalog (disk)   │◄──── datasets.jsonl + meta
│  Working (memory) │◄──── turn_snapshots
└────────┬─────────┘
         │
 aggregate_data 调用前
         │
         ▼
┌──────────────────┐
│ Ambiguity gate   │  规则：是否需语义解析？
└────────┬─────────┘
         │ yes
         ▼
┌──────────────────┐
│ Intent resolver  │  LLM 或内部小模型 / 规则+LLM 混合
│ (结构化输出)      │
└────────┬─────────┘
         │ DatasetBindingDecision
         ▼
┌──────────────────┐
│ Policy validate  │  硬规则：跨 turn、行数与 declared scope
└────────┬─────────┘
         ▼
   aggregate 执行
```

**降级**：resolver 超时/失败 → 返回 Error + `list_datasets` + 要求模型带 `dataset_id` 重试（不静默猜）。

---

## 4. 核心数据结构

### 4.1 `DatasetBindingDecision`（resolver 唯一输出）

```yaml
scope: chain_slice | class_wide | prior_turn_dataset | explicit_dataset
dataset_id: ds_xxx          # 优先于 result_ref
result_ref: optional        # 可由 catalog 解析
confidence: high | medium | low
rationale: "一句中文，写入 meta 供调试"
overrides_model_ref: true | false   # 是否覆盖模型传入的 ref
```

| scope | 含义 | 典型题干 |
|-------|------|----------|
| `chain_slice` | 本回合某次 **limit/top-N/「这些」**  query | 「汇总这 10 条」 |
| `class_wide` | 本班/本资源 **全量**（可复用本回合全量 ref 或要求新 query） | 「Class1 整体情况」 |
| `prior_turn_dataset` | 明确引用历史 | 「用刚才那份最低分列表」 |
| `explicit_dataset` | 模型已正确给出 id | 低歧义 |

### 4.2 Resolver 输入（必须有语义上下文）

| 字段 | 来源 |
|------|------|
| `teacher_message` | 当前 user turn 原文（或压缩后摘要，≤500 字） |
| `recent_assistant_plan` | 可选：上一条 assistant 是否承诺了「先 10 条再汇总」 |
| `catalog_summary` | `list_datasets` 同等信息：id、rows、limit、resource、user_turn、is_current_turn |
| `model_aggregate_args` | 模型拟传的 input / metrics / bind |
| `ambiguity_reason` | gate 触发原因码 |

**不再**把 `bind` 当作权威意图；可保留为**模型建议**，resolver 可忽略。

---

## 5. 歧义门控（Ambiguity gate）— 何时走语义层

满足 **任一** 即触发 Intent resolver（可配置）：

| 码 | 条件 |
|----|------|
| `MULTI_CANDIDATE` | 本回合 ≥2 个 dataset，且同时存在 slice + broad |
| `EXPLICIT_REF_MISMATCH` | 模型写了 ref，但与 catalog 中另一候选更贴合「切片/全班」且分差超过弱阈值 |
| `METRICS_SCOPE_CONFLICT` | 如 `count`+`mean` on 2.3 万行，但上一条 tool 为 limit=10 |
| `CROSS_TURN_REF` | result_ref 来自 prior turn（无 dataset_id） |
| `MODEL_BIND_UNTRUSTED` | 未传 dataset_id 且传了 bind=auto |
| `USER_REQUESTED` | 配置：analyze 模式下一律 resolver（成本高，仅调试） |

**不触发**：本回合仅 1 个 dataset，且模型 `dataset_id` 与 catalog 一致。

---

## 6. Intent resolver 实现选项（推荐组合）

### 阶段 A（推荐先做）：**专用小轮 LLM + 结构化 JSON**

- **时机**：`aggregate_data` 在 `inject_data_tool_context` 内，gate 为 true 时同步调用（同进程，非再暴露给主模型一轮 tool）。
- **模型**：可与主 agent 同模型，但 **max_tokens 极小**（仅 JSON）；或更小/更便宜的模型。
- **Prompt 要点**：
  - 只选 catalog 里已有的 `dataset_id`；
  - 区分「这 N 条/上述/刚才的列表」vs「全班/整体/偏科」；
  - 第二问全班 **不要** 选 limit=10 的 id；
  - 输出 schema 固定，便于校验。
- **校验**：`dataset_id` 必须在 catalog；`scope=class_wide` 时候选须 `is_broad_scan` 或提示先 `query_data` 无 limit。

**优点**：真正读题干；与现有工具链兼容。  
**缺点**：延迟 + token；需防 resolver 幻觉 id。

### 阶段 B：**主模型显式两步（产品层）**

- 工具拆分或强制流程：
  1. `resolve_dataset_binding(question_scope, metrics_hint)` → 返回 `dataset_id`
  2. `aggregate_data(input={dataset_id}, ...)`
- 主模型多一轮 tool，**意图由主模型在 step1 陈述**，runtime 只校验。

**优点**：可解释、可展示给用户。  
**缺点**：多一轮可见 latency；模型仍可能跳过 step1。

### 阶段 C：**Planner / todo 写死 binding（辅助，非充分）**

- `todo_write` 步骤增加 `data_scope: slice_10 | class1_full`；
- resolver 可读当前 in_progress 步骤。

**优点**：便宜。  
**缺点**：todo 常不更新；不能替代 A。

### 不推荐单独做

- 纯关键词（「这些」「全班」）— 易漏、易误判，仅可作 gate 辅助。
- 继续加厚 `bind` 加减分 — 已证明不够（Q1 即例）。

**推荐路径**：**A（内部 resolver）为主 + gate 减量 + B 在 SKILL 里鼓励显式 `dataset_id` + C 可选增强**。

---

## 7. 与现有组件的关系

| 组件 | 调整后角色 |
|------|------------|
| `datasets.jsonl` / `list_datasets` | resolver 输入；错误时给人/模型看 |
| `turn_snapshots` | 候选枚举；附带「本批顺序」写入 meta 供 resolver |
| `bind` auto/chain/fresh | **降级为 hint**；resolver 可写入 trace，默认不单独决定 |
| `binding_compat` 打分 | 保留作 **Policy validate**（resolver 选 slice 但 metrics 要 count_distinct 全班 → warn/error） |
| `explicit ref` 无条件信任 | **取消**；resolver 或 validate 可覆盖并写 `meta.ref_overridden` |

---

## 8. 执行流程（aggregate 一次调用的内部步骤）

1. 收集本回合 + catalog 候选 → `BindingContext`。
2. `ambiguity_gate` → 若 false：`pick_single_candidate()` + validate → 结束。
3. 若 true：调用 `resolve_binding_intent(ctx)` → `DatasetBindingDecision`。
4. `validate_decision(decision, ctx)`：
   - id 存在；
   - `chain_slice` → 候选必须有 limit 或 rows≤N；
   - `class_wide` → 候选须 broad，否则 Error「请先无 limit query」。
5. 写回 `input.dataset_id` / `result_ref`；`meta.binding_trace`。
6. 执行原有 `execute_aggregate`。

**失败**：不 aggregate；返回 Error + catalog + 建议「先 query / 用 list_datasets」。

---

## 9. 观测与评测

- **日志**：`binding_resolver_invoked`, `ambiguity_code`, `decision`, `overridden_model_ref`。
- **黄金用例**（自动化）：
  - Q1 类：limit=10 + 全量并行 → 汇总 10 条 → 必须 ds_slice。
  - Q2 类：新问全班 → 必须 ds_broad（可跨 turn 复用 Class1 全量 id）。
  - 跨 turn：「用刚才那份」→ 必须显式 prior id。
- **指标**：绑定纠错率、aggregate 后行数与预期不一致的告警。

---

## 10. 分阶段落地

| 阶段 | 交付 | 状态 |
|------|------|------|
| **S0** | gate 埋点 → `meta.binding_trace` | ✅ |
| **S1** | 跨 turn / 陈旧 ref 硬规则 + validate | ✅ `binding_pipeline.py` |
| **S2** | 内部 Intent resolver（LLM + 启发式兜底） | ✅ `intent_resolver.py`，`BINDING_RESOLVER_DISABLE_LLM=1` 测启发式 |
| **S3** | 工具 `resolve_dataset_binding` | ✅ |
| **S4** | todo `data_scope` + 回答自检 | 未做 |

**废弃计划**：长期不再扩展 `bind` 三档的加减分逻辑；文档标明 deprecated。

---

## 11. Resolver prompt 要点（草案）

**System**：你是数据集绑定器，只从给定 catalog 选一个 `dataset_id`，不执行 SQL。

**User**：

- 教师问题：…
- 本回合 query 摘要：（id, limit, rows, resource, 顺序）
- 模型 aggregate 意图：（metrics, 传入 ref）
- 触发原因：MULTI_CANDIDATE

**规则摘要**：

- 「这些/上述/刚查的 N 条」→ `chain_slice` 且选 limit 最小/最近 slice。
- 「全班/整体/规模/偏科」→ `class_wide` 且选无 limit 或 rows≈rows_scanned。
- 新问题不要默认上一题的 slice，除非题干明确延续。

---

## 12. 风险与对策

| 风险 | 对策 |
|------|------|
| Resolver 幻觉 dataset_id | 白名单校验；无效则 Error |
| 延迟 | 仅 gate 触发；缓存同 turn 相同题干+catalog 的 decision |
| 与主模型重复推理 | S2 内部调用对用户透明；S3 可选暴露 |
| 成本 | 小 max_tokens；可考虑更小模型 |

---

## 13. 一句话

**绑定 = .catalog 枚举候选 + 歧义门控 +（必要时）语义 resolver 读教师句选 dataset_id + 硬规则校验**；  
`bind` 三档不再扮演「意图」，只作兼容与 trace。
