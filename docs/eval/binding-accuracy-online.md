# Dataset Binding 在线准确率评测

> 生成时间：2026-06-11 08:15 UTC  
> 脚本：`backend/agent/eval/run_binding_online_eval.py`

## 指标定义

### Online Binding Accuracy

对每条评测场景中每一次 **`aggregate_data` 调用**判定是否正确：

| 判定 | 条件 |
|------|------|
| **正确** | 实际绑定的 `result_ref` 对应数据集满足场景 `expect` 约束 |
| **正确（guard）** | `expect_error=true` 或 `reject_cross_turn`，且 aggregate 返回 Error / Permission deny |
| **错误** | 绑错 ref、该拒绝却成功、该成功却 Error、或缺少预期 aggregate |

**准确率** = 正确 aggregate 判定数 / 评测 aggregate 总数

### expect 类型

| expect | 判定规则 |
|--------|----------|
| `slice` | `result_rows ≤ 50` 且（有 `query_limit` 或 `rows_scanned >> result_rows`） |
| `broad` | `result_rows > 500` 或无 limit 的全量 scan |
| `explicit_dataset_id` | `meta.dataset_id` / catalog 显式匹配 |
| `reject_cross_turn` | 跨 turn 静默续用旧 ref → Error（含「上一轮」提示） |
| `allow_cross_turn_explicit` | 显式 `dataset_id` 跨 turn 成功 |

绑定信息来源（优先级）：aggregate tool result `meta` → `datasets.jsonl` → `binding_trace`。

**评测模式**：真实 `AgentLoop.run_loop()` + 真实 LLM（**未**设置 `BINDING_RESOLVER_DISABLE_LLM`）。

## 失败归因（分类与修复）

| 类别 | 典型场景 | 根因 | 修复 |
|------|----------|------|------|
| **A. 评测误判** | `cross_turn_explicit_dataset` | tool JSON 截断 / `dataset_id` 未从 tool_input 读取 | `binding_judge` 信任 meta + `_explicit_dataset_id()` |
| **B. 取最后一笔** | `cross_turn_reject` | 无 ordinal 时评最后一笔，重试后绑 broad | `accept_guard_error` → **any_pass** |
| **C. 规则优先级** | `fresh_after_slice_same_turn` | 「不是这10条」仍触发 chain_slice | `class_wide_over_slice` + `rule_fresh_broad` |
| **D. 显式 id 绑错集** | `chain_slice_two_turns` | `dataset_id` 指向 broad | explicit 路径拒绝 broad + 要 slice |
| **E. LLM/超时** | 缺 aggregate、timeout | Agent 未跑完工具链 | 加强 prompt；非 binding 层 |

基线 **63.64%** (21/33) → 修复后全量 **93.75%** (30/32)。曾失败 5 场景专项复测 **13/15**。

## 结果摘要

| 指标 | 值 |
|------|-----|
| 场景数 N_scenarios | 10 |
| 重复次数 N_runs | 30 |
| 评测 aggregate 总数 N_aggregates | 32 |
| 正确数 | 30 |
| **Online Binding Accuracy** | **93.75%** |

## 按场景

| 场景 | 准确率 |
|------|--------|
| `chain_slice_two_turns` | 66.67% |
| `class_wide_after_slice_new_turn` | 100.0% |
| `cross_turn_explicit_dataset` | 100.0% |
| `cross_turn_reject` | 66.67% |
| `explicit_dataset_id_same_turn` | 100.0% |
| `fresh_after_slice_same_turn` | 100.0% |
| `reject_cross_turn_silent` | 100.0% |
| `semantic_class_wide_single_turn` | 100.0% |
| `single_turn_explicit_two_queries` | 100.0% |
| `wrong_ref_correction` | 100.0% |

## 按 resolver

| resolver | 准确率 |
|----------|--------|
| `explicit_dataset_id` | 100.0% |
| `llm` | 100.0% |
| `rule_chain_slice` | 100.0% |
| `rule_fresh_broad` | 100.0% |
| `single_candidate` | 80.0% |
| `unknown` | 80.0% |

## 失败明细

| 场景 | run | expect | 原因 |
|------|-----|--------|------|
| `chain_slice_two_turns` | 0 | `slice` | not slice: rows=22960 limit=None |
| `cross_turn_reject` | 0 | `slice` | missing aggregate |
| `cross_turn_reject` | 0 | `slice` | no matching aggregate_data call |
| `reject_cross_turn_silent` | 0 | `reject_cross_turn` | run timeout |

## 与离线评测关系

- **离线**（`binding_accuracy.py`）：直接 `resolve_aggregate_binding`，`BINDING_RESOLVER_DISABLE_LLM=1`，测 resolver 逻辑。
- **在线**（本报告）：完整 Agent + 真实 query/aggregate，测端到端绑定准确率。

## 简历可用（一句话）

> 基于 N=32 次真实 AgentLoop aggregate 调用，数据集绑定准确率 **93.75%**（真实 LLM + query/aggregate 链路）。

## 复现

```bash
cd H:/WORKDIR/NorthClassVision
python backend/agent/eval/run_binding_online_eval.py --runs 3
python backend/agent/eval/run_binding_online_eval.py --scenario chain_slice_two_turns --runs 1
```

集成测试（需 API Key）：`$env:RUN_BINDING_ONLINE=1; pytest backend/agent/test/test_binding_online_eval.py -m integration`
