# 新会话需求 Prompt：通用 Agent Benchmark Harness

> **用法**：新开 Cursor 会话后，把下方「可复制 Prompt」整段粘贴给 Agent 即可。  
> **分支建议**：`git checkout -b feat/agent-benchmark main`  
> **版本**：2026-07-20（含指标分层 + 轮次/会话/runs 协议）  
> **原则**：先建可复用 harness，再做 system/cache、binding、loop 等优化；用同一 runner 跑场景、统计不同指标。

---

## 可复制 Prompt

```text
# 任务：为 NorthClassVision Agent 建立通用 Benchmark Harness

## 0. 工作方式
- 仓库：NorthClassVision，以最新 `main` 为起点。
- 新分支：`feat/agent-benchmark`（或同类名）。
- 先阅读本仓库现有 eval 资产与文档，给出简短设计方案并得到确认，再写实现计划与代码（避免一上来大重构）。
- 始终用中文与用户沟通；提交仅在用户明确要求时创建。

## 1. 背景与原则
- 目标：先建立**一套通用 benchmark**，再做 system/cache、binding、loop 等优化；否则无法证明「省了多少、有没有伤正确性」。
- 「通用」= **一套 Runner + 可插拔 Metrics**，不是门禁与效率两套框架，也不是每种能力各写一套。
- 同一场景跑一遍，应同时产出正确性、binding、tools/loop、成本延迟等指标；报告按指标列对照。
- 产品是工具型数据 Agent：优先 **工具结果正确 + 绑定正确 + loop 不炸**；弱化通用文采 / 纯 RAG faithfulness / 无显式计划时的 Plan Quality。

## 2. 现有可复用资产（必须优先提拔，勿从零重写）
1. 在线 runner：`backend/agent/eval/run_binding_online_eval.py`
   - SessionManager + AgentLoop、多 turn、timeout、dry-run、JSON/MD 报告
2. 判定器：`backend/agent/eval/binding_judge.py`
3. Fixtures：`backend/agent/eval/fixtures/binding_online_scenarios.json`（约 10 条，1–2 turn）
4. 离线快门禁：`backend/agent/eval/binding_accuracy.py`（纯 resolver，`BINDING_RESOLVER_DISABLE_LLM=1`）
5. 文档基线：`docs/eval/binding-accuracy.md`、`docs/eval/binding-accuracy-online.md`
6. Langfuse：`backend/agent/common/langfuse_tracing.py`（stream usage / cached tokens）
   - 探针：`backend/agent/scripts/langfuse_cache_probe.py`、`run_langfuse_cache_live.py`
7. pytest：`backend/agent/test/test_binding_online_eval.py`（`RUN_BINDING_ONLINE=1` + integration）
8. 相关产品能力（场景可覆盖）：composer 本轮 scope / 附件（人、班、周、知识点、上次查询、视图、报告）、
   `session/ui_scope.py`、`compose_llm_user_content` 本轮并入 user（利于 prefix cache）

## 3. 目标架构
Scenario → Runner（提拔 online eval 脚手架）→ Trace（统一事件流）
→ 可插拔 Metrics / Judges → 统一 Report（JSON + MD）

Trace 至少应能汇总：
- turn / tool_call 序列与参数摘要
- continue_reason、timeout、missing expected tool
- duration（端到端 + 可选 per-turn）
- usage：prompt / completion / cached tokens（本地 usage 优先；Langfuse 按 eval metadata 过滤作补充）
- 失败归因 tags（见下）

推荐实现路径：**提拔现有 binding online eval 为通用 runner**；binding 降为第一个 Metric/Judge 插件。
不要新建与现有 eval 完全平行的第二套框架。

## 4. Metrics 分层（必须按优先级落地）

### P0 — 正确性与产品契约（门禁向）
| 指标 | 测什么 | 判据 |
|------|--------|------|
| task_success | 用户目标是否达成 | 场景最终断言（数值/结构/拒绝）；复杂处可挂 Python judge；可选 LLM-as-judge 但非首版依赖 |
| binding_accuracy | slice / broad / explicit_dataset_id / 跨 turn guard | 复用现有 `binding_judge` |
| tool_correctness | 该调的工具是否调了 | expect_tools / forbid_tools |
| arg_correctness | 关键参数是否合格 | filter、limit、group_by、dataset_id、bind 等字段级断言 |
| scope_contract | 本轮 UI scope / 附件是否被遵守 | 注入的 user/scope + 工具侧 filter_context |
| guard_reject | 该拒绝时是否拒绝 | expect_error / Permission deny / reject_cross_turn |

### P1 — 轨迹与 Loop 健康（回归 + 优化）
| 指标 | 测什么 |
|------|--------|
| step_efficiency | 实际 tool 步数 vs 场景标注的最优/上限（expect_max_tool_calls 等） |
| loop_health | timeout、缺预期工具、无效重试、oscillation、compact 滥用 |
| failure_tags | 归因：judge_mislabel / missing_tool / rule_priority / explicit_id_wrong / llm_timeout（对齐 docs 中 A–E） |

### P2 — 成本 / 延迟 / Cache（效率轨；与正确性同报告，默认不做硬门禁）
| 指标 | 测什么 |
|------|--------|
| latency | 端到端 p50/p95；可选 TTFT / per-turn |
| tokens_cost | input/output tokens；cost 估算；**cost_per_successful_task** |
| cache_hit_rate | cached tokens / 可缓存前缀稳定性（同 system 下第 2+ 次） |
| report_path（可选） | write/edit/review_report、visual_links 是否产出 |

统计口径：
- 主正确性：pass@1 + pass@k（见运行协议）
- Binding 子指标：继续按 aggregate 判定数算 accuracy（兼容现有报告）
- 效率指标：优先在**成功 run**上报告 median（避免失败 inflates）

## 5. 场景期望契约
- 优先**声明式 JSON** fixture，便于 CI 与 diff。
- 复杂断言允许挂 **Python judge 插件**（JSON + judge 双轨）。
- Schema 草案应覆盖（实现时可微调命名，但语义要对齐）：
  - id, mode, filter_context / ui_scope
  - turns: string[]（单场景上限见下）
  - expect_aggregates / expect_binding（兼容现有）
  - expect_tools / forbid_tools
  - expect_args（字段级）
  - expect_task / assert_*（最终数值或结构）
  - expect_error / accept_guard_error
  - expect_max_turns / expect_max_tool_calls
  - tags: [binding|tools|scope|guard|numeric|efficiency|...]
- 兼容迁移：现有 `binding_online_scenarios.json` 应几乎不改即可被新 runner 跑通（binding metric 继续工作）。

## 6. 规模与运行协议（v1 必须遵守）

### 术语
- Turn：同 session 一次 user → agent 完整回合（可含多 tool call）
- Session / Scenario：一条 fixture = 一个新 session（隔离 filter_context / datasets）
- Run：同一 scenario 整条再跑一遍（测非确定性）

### Turns（最少轮次）
| 类型 | 最少 turns | v1 占比 | 覆盖点 |
|------|------------|---------|--------|
| 单轮闭环 | 1 | ~40% | 语义全班、单次 query+agg、scope 注入 |
| 同轮多步 | 1（多 tool） | ~20% | 两份 query+两次 agg、wrong_ref |
| 跨轮续用/拒绝 | 2 | ~30% | chain slice、reject silent、explicit id、口径切换 |
| 长链/报告 | 2–3 | ~10% | list→bind→agg→visual/report |

硬约束：
- 场景平均 ≤ 2 turns；**单场景上限 3 turns**
- 跨 turn 行为必须用独立 session 的 2-turn 场景，不要塞进 1-turn 指令假装

### Sessions（场景数）
按能力桶凑齐，勿盲目堆量：

| 桶 | v1 场景数 | 说明 |
|----|-----------|------|
| Binding / 数据链 | 8–12 | 沿用并微扩展现有 online fixtures |
| 工具选择与参数 | 6–10 | query limit、enrich、list_datasets、forbid 乱调 |
| Scope / 附件 | 4–6 | 班/人/周/知识点/上次查询/视图/报告 |
| Guard / 权限 | 3–5 | 跨 turn reject、mode deny |
| 任务成功（可程序断言） | 5–8 | 最终 mean/count 等 |
| 效率探针 | 2–3 | 固定短任务测 cache/latency |
| **合计** | **约 30–40** | 1 scenario = 1 新 session |

说明：现有 online 仅 ~10 sessions，只够 binding 子套件；通用 harness v1 目标 ~35。

### Runs（重复次数）
| 用途 | runs / scenario | 说明 |
|------|-----------------|------|
| 开发冒烟 | 1 | 改 prompt/规则后快速看挂点 |
| **日常回归（默认）** | **3** | 看稳定性；失败策略 any_pass / majority 可配置 |
| 发版 / 基线 | 8–10 | 报 pass@1 + pass@3（或 pass@8） |
| Flaky 专项 | 10–30 | **仅对不稳定子集**加跑；禁止默认全量 30 |

默认工作量量级：~35 scenarios × 3 runs ≈ 105 session-runs。
CLI 需支持：`--runs`、`--scenario`、`--tags`、`--dry-run`、timeout。

## 7. 第一版交付物
1. 通用 runner（提拔自 `run_binding_online_eval.py`）+ Trace 汇总
2. Metrics 插件：至少 P0 全开；P1 核心（step_efficiency + loop_health）；P2 基础 usage/latency/cache
3. binding 作为第一个插件完整迁移；旧命令/文档可薄封装兼容或明确迁移说明
4. v1 fixtures：~30–40 scenarios（含原 binding 集），按 tags 可筛选
5. 离线 binding accuracy 仍作快门禁；在线套件用 env 开关（如 `RUN_AGENT_ONLINE=1`，可兼容旧 `RUN_BINDING_ONLINE`）
6. 统一报告：JSON + MD（正确性表 + 效率表 + 失败明细 + 按 tag/场景分解）
7. docs：如何加场景、如何读报告、冒烟/回归/发版怎么跑、与旧 binding eval 关系
8. pytest：dry-run / schema；integration 需 API Key + env 开关

## 8. 明确不做（本阶段）
- 不要先做「todo/datasets 移出 system」等优化实验，除非 harness 已能对比 before/after
- 不要新建与现有 eval 完全平行的第二套框架
- 不要默认全量 `--runs 30`
- 不要把单场景做成 >3 turns 的超长剧本
- 不要把「回答文采」或无契约的 LLM-as-judge 当唯一门禁

## 9. 建议目录（设计时可微调，需在方案中说明）
- `backend/agent/eval/runner.py`（或 `bench/` 子包，但应复用 eval 包，避免双轨）
- `backend/agent/eval/trace.py`
- `backend/agent/eval/metrics/`（binding.py, tools.py, loop.py, cost.py, task.py …）
- `backend/agent/eval/fixtures/scenarios/`（按 tag 分文件或单文件 + tags）
- `docs/eval/agent-benchmark.md`（主文档）
- 报告输出：`data/eval/` + `docs/eval/`（对齐现有 binding 报告路径习惯）

## 10. 验收标准
- 同一命令跑一套场景，报告里同时有 P0 正确性与 P2 效率列
- 原 binding online 场景在新 harness 下结果可解释，且迁移成本低
- `--dry-run` 可不花 API 校验加载与 schema
- 文档写清：冒烟 runs=1、回归 runs=3、发版 runs=8
- 用户确认设计后再大规模加场景/改 runner

## 11. 请你现在开始
1. 阅读第 2 节列出的文件与 `docs/eval/binding-accuracy-online.md`
2. 给出简短设计：目录结构、scenario schema 草案、metrics 列表、旧 binding eval 迁移路径、v1 场景桶分配
3. 等确认后再实现
```

---

## 附：开分支命令

```bash
git checkout main
git pull
git checkout -b feat/agent-benchmark
```

## 附：与调研结论的对应关系

| 决策 | 取值 |
|------|------|
| 架构 | 一套 Runner + 可插拔 Metrics |
| 提拔起点 | `run_binding_online_eval.py` + `binding_judge.py` |
| v1 场景数 | ~30–40 sessions |
| 单场景 turns | 多数 1–2，上限 3 |
| 默认 runs | 3（冒烟 1 / 发版 8–10 / flaky 子集 10–30） |
| 主指标 | pass@1 + pass@k；binding 按 aggregate 判定数 |
| 效率 | 与正确性同报告；默认非硬门禁 |
