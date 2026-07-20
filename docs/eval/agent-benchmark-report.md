# Agent Benchmark 报告

> 生成时间：2026-07-20 15:01 UTC  
> 脚本：`backend/agent/eval/run_agent_benchmark.py`

## 运行清单（manifest）

| 字段 | 值 |
|------|-----|
| benchmark_run_id | `20260720T140335Z-c7ae60f0` |
| model | `deepseek-v4-flash` |
| base_url | `https://api.deepseek.com` |
| git commit | `88ae1023fe84db9bf999481f5bb99df887f2fc7f` |
| scenario fingerprint | `7a8f3d1f86910ccc` |
| checkpoint | `H:\WORKDIR\NorthClassVision\data\eval\runs\20260720T140335Z-c7ae60f0\agent_benchmark.partial.jsonl` |
| Langfuse 筛选 | session `agent-bench-*` + `benchmark_run_id=20260720T140335Z-c7ae60f0` |

## 汇总

| 指标 | 值 |
|------|-----|
| 场景数 N_scenarios | 37 |
| runs / scenario | 3 |
| session-runs | 111 |
| pass 策略 | majority |
| **pass@1** | **59.46%** (22/37) |
| **pass@k** (≥1 run 过硬门禁) | **67.57%** (25/37) |
| Binding accuracy (aggregate 判定) | 66.67% (48/72) |
| **单 turn 中位延迟（推荐）** | 8.11s |
| **单 turn p95 延迟** | 34.15s |
| 单 turn 样本数 | 333 |
| 整场景中位延迟（通常 3 turns 合计） | 25.54s |
| 整场景 p95 延迟 | 62.64s |
| 成功 run 整场景中位 | 23.95s |
| 成功 run 整场景 p95 | 53.98s |
| 全部 run 估算总成本 | $0.3494 |
| 全部 run 中位成本 | $0.002493 |
| 全部 run p95 成本 | $0.006912 |
| cost_per_successful_task (估) | $0.00242 |

## Metrics

| Metric | passed/total | pct |
|--------|--------------|-----|
| `arg_correctness` | 30/36 | 83.33% |
| `binding_accuracy` | 48/72 | 66.67% |
| `cache_hit_rate` | 111/111 | 100.0% |
| `failure_tags` | 111/111 | 100.0% |
| `forbid_tools` | 36/36 | 100.0% |
| `guard_reject` | 17/18 | 94.44% |
| `latency` | 111/111 | 100.0% |
| `loop_health` | 63/111 | 56.76% |
| `scope_contract` | 14/15 | 93.33% |
| `step_efficiency` | 134/138 | 97.1% |
| `task_success` | 38/63 | 60.32% |
| `tokens_cost` | 111/111 | 100.0% |
| `tool_correctness` | 50/81 | 61.73% |

## 按场景（正确性 + 效率）

| 场景 | tags | pass | binding | median latency | median tokens (in/out/cache) |
|------|------|------|---------|----------------|------------------------------|
| `chain_slice_two_turns` | binding | 3/3 (✓) | 100.0% | 24.11s | 95819/1934/89472 |
| `class_wide_after_slice_new_turn` | binding | 2/3 (✓) | 66.67% | 35.69s | 187046/2840/173888 |
| `single_turn_explicit_two_queries` | binding,tools | 0/3 (✗) | 33.33% | 35.84s | 201871/2726/185600 |
| `wrong_ref_correction` | binding | 3/3 (✓) | 100.0% | 33.09s | 200314/2593/182016 |
| `cross_turn_reject` | binding,guard | 3/3 (✓) | 100.0% | 20.49s | 85023/1756/79360 |
| `cross_turn_explicit_dataset` | binding,tools | 0/3 (✗) | 100.0% | 27.31s | 117679/2604/109952 |
| `semantic_class_wide_single_turn` | binding,task | 0/3 (✗) | 0.0% | 73.91s | 472863/5851/444160 |
| `fresh_after_slice_same_turn` | binding | 3/3 (✓) | 100.0% | 22.11s | 105958/1518/92800 |
| `reject_cross_turn_silent` | binding,guard | 1/3 (✗) | 33.33% | 37.8s | 187160/3279/173184 |
| `explicit_dataset_id_same_turn` | binding,tools | 0/3 (✗) | 0.0% | 20.94s | 85537/1980/79488 |
| `chain_slice_then_broad_switch` | binding | 3/3 (✓) | 100.0% | 20.26s | 122439/1353/108032 |
| `two_turn_list_then_explicit_bind` | binding,tools | 0/3 (✗) | 66.67% | 17.96s | 84074/1502/78592 |
| `efficiency_short_query` | efficiency | 3/3 (✓) | — | 16.73s | 65088/1446/60544 |
| `efficiency_query_agg_budget` | efficiency,task | 2/3 (✓) | 66.67% | 30.61s | 182847/2560/169600 |
| `guard_reject_cross_turn_silent` | guard,binding | 2/3 (✓) | 66.67% | 26.99s | 143451/2227/129344 |
| `guard_consult_denies_query` | guard | 2/3 (✓) | — | 15.89s | 37844/968/33536 |
| `guard_cross_turn_accept_or_slice` | guard,binding | 2/3 (✓) | 66.67% | 18.48s | 90415/1751/84672 |
| `guard_no_silent_reuse_after_broad` | guard,binding | 3/3 (✓) | 100.0% | 19.55s | 133648/1189/121472 |
| `scope_class_chip` | scope | 3/3 (✓) | — | 46.47s | 301267/4478/276096 |
| `scope_week_range` | scope | 3/3 (✓) | — | 53.97s | 284111/5445/258432 |
| `scope_selected_students` | scope,scope-extended | 2/3 (✓) | — | 40.19s | 215540/3067/195648 |
| `scope_knowledge_attachment` | scope,scope-extended | 2/3 (✓) | — | 49.47s | 339154/4973/311744 |
| `scope_view_and_report_attachment` | scope,scope-extended | 0/3 (✗) | — | 69.79s | 432198/6835/401664 |
| `task_class_mean_score` | task,numeric | 0/3 (✗) | 0.0% | 61.25s | 354419/6458/330496 |
| `task_slice_count` | task,numeric,binding | 3/3 (✓) | 100.0% | 27.35s | 110880/3114/101248 |
| `task_two_step_query_agg` | task | 0/3 (✗) | 100.0% | 20.62s | 84489/2101/78336 |
| `task_list_bind_agg_chain` | task,binding,tools | 0/3 (✗) | 33.33% | 20.83s | 85895/2117/80000 |
| `task_enrich_score_rate_path` | task,tools | 0/3 (✗) | — | 25.54s | 107467/2565/98560 |
| `task_status_and_no_forbidden` | task,tools | 3/3 (✓) | 100.0% | 20.91s | 156061/1391/141184 |
| `tools_query_limit_10` | tools | 3/3 (✓) | — | 21.22s | 77665/1787/69632 |
| `tools_forbid_report_on_simple_query` | tools | 3/3 (✓) | — | 18.32s | 127476/1038/114688 |
| `tools_list_datasets_after_query` | tools | 3/3 (✓) | — | 15.96s | 67132/1468/62848 |
| `tools_enrich_then_aggregate` | tools | 0/3 (✗) | — | 32.6s | 127782/2990/118528 |
| `tools_inspect_schema_before_query` | tools | 3/3 (✓) | — | 23.91s | 67371/2141/61312 |
| `tools_query_with_class_filter` | tools | 3/3 (✓) | — | 48.13s | 288379/4406/265984 |
| `tools_aggregate_requires_metrics` | tools,task | 0/3 (✗) | 33.33% | 52.79s | 384293/4520/358528 |
| `tools_no_compact_on_short_task` | tools,efficiency | 3/3 (✓) | — | 13.68s | 40595/1238/38016 |

## 失败明细

| 场景 | run | metric | 原因 |
|------|-----|--------|------|
| `class_wide_after_slice_new_turn` | 0 | `binding_accuracy` | not broad: rows=1 limit=None |
| `single_turn_explicit_two_queries` | 0 | `binding_accuracy` | unexpected error: Error: result_ref 来自上一轮提问，不能自动续用。请 list_datasets，再在 input.dataset_id 中显式引用；仅当班级/周次/过滤条件变化时才重新 query_data。
最近数据集（指代：看 grain/label；续算传 dataset_id；勿把「聚合表」当「原始行」）：
 |
| `single_turn_explicit_two_queries` | 0 | `binding_accuracy` | not broad: rows=10 limit=10 |
| `single_turn_explicit_two_queries` | 0 | `tool_correctness` | missing=['query_data']; count=2 < min=4 |
| `single_turn_explicit_two_queries` | 1 | `binding_accuracy` | unexpected error: Error: dataset_id='ds_b3740cf8cb4b' 为全量（22960 行），但教师话要求切片/「这些记录」口径。请 list_datasets 后改选 limit 切片 dataset_id。
最近数据集（指代：看 grain/label；续算传 dataset_id；勿把「聚合表」当「原始行」） |
| `single_turn_explicit_two_queries` | 2 | `binding_accuracy` | unexpected error: Error: dataset_id='ds_38dbcfda583b' 为全量（22960 行），但教师话要求切片/「这些记录」口径。请 list_datasets 后改选 limit 切片 dataset_id。
最近数据集（指代：看 grain/label；续算传 dataset_id；勿把「聚合表」当「原始行」） |
| `cross_turn_explicit_dataset` | 0 | `tool_correctness` | missing=['list_datasets'] |
| `cross_turn_explicit_dataset` | 1 | `tool_correctness` | missing=['list_datasets'] |
| `cross_turn_explicit_dataset` | 2 | `tool_correctness` | missing=['list_datasets'] |
| `semantic_class_wide_single_turn` | 0 | `binding_accuracy` | not broad: rows=1 limit=None |
| `semantic_class_wide_single_turn` | 1 | `binding_accuracy` | missing aggregate |
| `semantic_class_wide_single_turn` | 1 | `task_success` | no successful aggregate_data |
| `semantic_class_wide_single_turn` | 1 | `task_success` | metric op=mean field=score not found |
| `semantic_class_wide_single_turn` | 2 | `binding_accuracy` | not broad: rows=1 limit=None |
| `reject_cross_turn_silent` | 0 | `binding_accuracy` | dataset user_turn=2 not prior to current=2 |
| `reject_cross_turn_silent` | 2 | `binding_accuracy` | no catalog record for bound ref/dataset_id |
| `explicit_dataset_id_same_turn` | 0 | `binding_accuracy` | missing aggregate |
| `explicit_dataset_id_same_turn` | 0 | `tool_correctness` | missing=['query_data', 'list_datasets', 'aggregate_data'] |
| `explicit_dataset_id_same_turn` | 1 | `binding_accuracy` | missing aggregate |
| `explicit_dataset_id_same_turn` | 1 | `tool_correctness` | missing=['query_data', 'list_datasets', 'aggregate_data'] |
| `explicit_dataset_id_same_turn` | 2 | `binding_accuracy` | dataset_id mismatch meta='ds_744a0576d5d1' bound='ds_71e00536edb2' |
| `explicit_dataset_id_same_turn` | 2 | `tool_correctness` | missing=['list_datasets'] |
| `two_turn_list_then_explicit_bind` | 0 | `tool_correctness` | missing=['list_datasets'] |
| `two_turn_list_then_explicit_bind` | 1 | `tool_correctness` | missing=['list_datasets'] |
| `two_turn_list_then_explicit_bind` | 2 | `binding_accuracy` | missing aggregate |
| `two_turn_list_then_explicit_bind` | 2 | `tool_correctness` | missing=['list_datasets'] |
| `efficiency_query_agg_budget` | 0 | `binding_accuracy` | missing aggregate |
| `efficiency_query_agg_budget` | 0 | `tool_correctness` | missing=['query_data', 'aggregate_data'] |
| `efficiency_query_agg_budget` | 0 | `task_success` | no successful aggregate_data |
| `efficiency_query_agg_budget` | 0 | `task_success` | metric op=mean field=score not found |
| `guard_reject_cross_turn_silent` | 1 | `binding_accuracy` | dataset user_turn=2 not prior to current=2 |
| `guard_consult_denies_query` | 2 | `guard_reject` | expected guard/permission error |
| `guard_cross_turn_accept_or_slice` | 2 | `binding_accuracy` | not slice: rows=1 limit=None |
| `scope_selected_students` | 1 | `tool_correctness` | missing=['get_current_filter_context'] |
| `scope_knowledge_attachment` | 1 | `tool_correctness` | missing=['query_data'] |
| `scope_view_and_report_attachment` | 0 | `tool_correctness` | missing=['get_current_filter_context'] |
| `scope_view_and_report_attachment` | 1 | `tool_correctness` | missing=['get_current_filter_context'] |
| `scope_view_and_report_attachment` | 2 | `tool_correctness` | missing=['get_current_filter_context'] |
| `task_class_mean_score` | 0 | `binding_accuracy` | missing aggregate |
| `task_class_mean_score` | 0 | `task_success` | no successful aggregate_data |
| `task_class_mean_score` | 0 | `task_success` | metric op=mean field=score not found |
| `task_class_mean_score` | 0 | `task_success` | no tool result |
| `task_class_mean_score` | 1 | `binding_accuracy` | missing aggregate |
| `task_class_mean_score` | 1 | `task_success` | no successful aggregate_data |
| `task_class_mean_score` | 1 | `task_success` | metric op=mean field=score not found |
| `task_class_mean_score` | 1 | `task_success` | no tool result |
| `task_class_mean_score` | 2 | `binding_accuracy` | missing aggregate |
| `task_class_mean_score` | 2 | `task_success` | no successful aggregate_data |
| `task_class_mean_score` | 2 | `task_success` | metric op=mean field=score not found |
| `task_class_mean_score` | 2 | `task_success` | no tool result |
| `task_two_step_query_agg` | 0 | `tool_correctness` | missing=['query_data'] |
| `task_two_step_query_agg` | 1 | `tool_correctness` | missing=['query_data'] |
| `task_two_step_query_agg` | 2 | `tool_correctness` | missing=['query_data'] |
| `task_list_bind_agg_chain` | 0 | `tool_correctness` | missing=['list_datasets'] |
| `task_list_bind_agg_chain` | 0 | `task_success` | tool not called: list_datasets |
| `task_list_bind_agg_chain` | 1 | `binding_accuracy` | missing aggregate |
| `task_list_bind_agg_chain` | 1 | `tool_correctness` | missing=['list_datasets', 'aggregate_data'] |
| `task_list_bind_agg_chain` | 1 | `task_success` | tool not called: list_datasets |
| `task_list_bind_agg_chain` | 1 | `task_success` | no successful aggregate_data |
| `task_list_bind_agg_chain` | 2 | `binding_accuracy` | missing aggregate |
| `task_list_bind_agg_chain` | 2 | `tool_correctness` | missing=['list_datasets', 'aggregate_data'] |
| `task_list_bind_agg_chain` | 2 | `task_success` | tool not called: list_datasets |
| `task_list_bind_agg_chain` | 2 | `task_success` | no successful aggregate_data |
| `task_enrich_score_rate_path` | 0 | `tool_correctness` | missing=['query_data', 'enrich_data'] |
| `task_enrich_score_rate_path` | 0 | `task_success` | no successful enrich_data |
| `task_enrich_score_rate_path` | 1 | `tool_correctness` | missing=['query_data', 'enrich_data'] |
| `task_enrich_score_rate_path` | 1 | `task_success` | no successful enrich_data |
| `task_enrich_score_rate_path` | 2 | `tool_correctness` | missing=['query_data', 'enrich_data'] |
| `task_enrich_score_rate_path` | 2 | `task_success` | no successful enrich_data |
| `tools_enrich_then_aggregate` | 0 | `tool_correctness` | missing=['query_data', 'enrich_data'] |
| `tools_enrich_then_aggregate` | 0 | `arg_correctness` | no enrich_data call for args check |
| `tools_enrich_then_aggregate` | 0 | `arg_correctness` | no enrich_data call for args check |
| `tools_enrich_then_aggregate` | 1 | `tool_correctness` | missing=['query_data', 'enrich_data'] |
| `tools_enrich_then_aggregate` | 1 | `arg_correctness` | no enrich_data call for args check |
| `tools_enrich_then_aggregate` | 1 | `arg_correctness` | no enrich_data call for args check |
| `tools_enrich_then_aggregate` | 2 | `tool_correctness` | missing=['query_data', 'enrich_data'] |
| `tools_enrich_then_aggregate` | 2 | `arg_correctness` | no enrich_data call for args check |
| `tools_enrich_then_aggregate` | 2 | `arg_correctness` | no enrich_data call for args check |
| `tools_aggregate_requires_metrics` | 0 | `binding_accuracy` | missing aggregate |
| `tools_aggregate_requires_metrics` | 0 | `tool_correctness` | missing=['query_data', 'aggregate_data'] |
| … | … | … | 另有 7 条 |

## 口径说明

- **硬门禁 (P0)**：binding / tools / args / scope / guard / task_success
- **效率 (P2)**：latency / tokens / cache — 同报告、默认非硬门禁；优先在成功 run 上取 median
- **Binding**：按 aggregate 判定数算 accuracy（兼容历史 online binding 口径）
- 冒烟 `--runs 1`；日常回归 `--runs 3`；发版 `--runs 8`

## 复现

```bash
python backend/agent/eval/run_agent_benchmark.py --dry-run
python backend/agent/eval/run_agent_benchmark.py --runs 3
python backend/agent/eval/run_agent_benchmark.py --tags binding --runs 1
```
