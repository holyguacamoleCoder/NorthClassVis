# Agent Benchmark 报告

> 生成时间：2026-07-20 12:30 UTC  
> 脚本：`backend/agent/eval/run_agent_benchmark.py`

## 运行清单（manifest）

| 字段 | 值 |
|------|-----|
| benchmark_run_id | `20260720T123049Z-bf4e95bd` |
| model | `deepseek-v4-flash` |
| base_url | `https://api.deepseek.com` |
| git commit | `7c343e61879a391bd54a30d990e7ac440acede00` |
| scenario fingerprint | `b60562bcfd682ab1` |
| checkpoint | `H:\WORKDIR\NorthClassVision\data\eval\agent_benchmark.partial.jsonl` |
| Langfuse 筛选 | session `agent-bench-*` + `benchmark_run_id=20260720T072730Z-e671148f` |

## 汇总

| 指标 | 值 |
|------|-----|
| 场景数 N_scenarios | 37 |
| runs / scenario | 3 |
| session-runs | 111 |
| pass 策略 | majority |
| **pass@1** | **51.35%** (19/37) |
| **pass@k** (≥1 run 过硬门禁) | **62.16%** (23/37) |
| Binding accuracy (aggregate 判定) | 61.11% (44/72) |
| **单 turn 中位延迟（推荐）** | 8.31s |
| **单 turn p95 延迟** | 35.08s |
| 单 turn 样本数 | 333 |
| 整场景中位延迟（通常 3 turns 合计） | 26.11s |
| 整场景 p95 延迟 | 65.48s |
| 成功 run 整场景中位 | 21.84s |
| 成功 run 整场景 p95 | 65.48s |
| 全部 run 估算总成本 | $1.6157 |
| 全部 run 中位成本 | $0.011046 |
| 全部 run p95 成本 | $0.036853 |
| cost_per_successful_task (估) | $0.008345 |

## Metrics

| Metric | passed/total | pct |
|--------|--------------|-----|
| `arg_correctness` | 29/36 | 80.56% |
| `binding_accuracy` | 44/72 | 61.11% |
| `cache_hit_rate` | 111/111 | 100.0% |
| `failure_tags` | 111/111 | 100.0% |
| `forbid_tools` | 36/36 | 100.0% |
| `guard_reject` | 17/18 | 94.44% |
| `latency` | 111/111 | 100.0% |
| `loop_health` | 6/111 | 5.41% |
| `scope_contract` | 0/15 | 0.0% |
| `step_efficiency` | 131/138 | 94.93% |
| `task_success` | 26/63 | 41.27% |
| `tokens_cost` | 111/111 | 100.0% |
| `tool_correctness` | 46/81 | 56.79% |

## 按场景（正确性 + 效率）

| 场景 | tags | pass | binding | median latency | median tokens (in/out/cache) |
|------|------|------|---------|----------------|------------------------------|
| `chain_slice_two_turns` | binding | 3/3 (✓) | 100.0% | 38.24s | 83542/1681/41984 |
| `class_wide_after_slice_new_turn` | binding | 3/3 (✓) | 100.0% | 21.74s | 104318/1781/29568 |
| `single_turn_explicit_two_queries` | binding,tools | 0/3 (✗) | 16.67% | 31.71s | 173594/2808/86912 |
| `wrong_ref_correction` | binding | 3/3 (✓) | 100.0% | 20.71s | 99708/1633/35968 |
| `cross_turn_reject` | binding,guard | 3/3 (✓) | 100.0% | 21.42s | 94668/1902/41728 |
| `cross_turn_explicit_dataset` | binding,tools | 1/3 (✗) | 100.0% | 101.6s | 1320821/8247/693632 |
| `semantic_class_wide_single_turn` | binding,task | 2/3 (✓) | 66.67% | 74.36s | 479848/6913/190400 |
| `fresh_after_slice_same_turn` | binding | 3/3 (✓) | 100.0% | 21.33s | 101587/1693/29184 |
| `reject_cross_turn_silent` | binding,guard | 1/3 (✗) | 33.33% | 25.86s | 139021/2251/52224 |
| `explicit_dataset_id_same_turn` | binding,tools | 0/3 (✗) | 0.0% | 24.45s | 69394/1591/29440 |
| `chain_slice_then_broad_switch` | binding | 3/3 (✓) | 100.0% | 20.48s | 118829/1462/31488 |
| `two_turn_list_then_explicit_bind` | binding,tools | 0/3 (✗) | 0.0% | 22.55s | 88585/2173/42752 |
| `efficiency_short_query` | efficiency | 3/3 (✓) | — | 13.98s | 52580/1112/28160 |
| `efficiency_query_agg_budget` | efficiency,task | 0/3 (✗) | 66.67% | 29.15s | 149896/2785/59392 |
| `guard_reject_cross_turn_silent` | guard,binding | 0/3 (✗) | 0.0% | 27.94s | 148712/2775/31744 |
| `guard_consult_denies_query` | guard | 2/3 (✓) | — | 14.66s | 33316/1004/21248 |
| `guard_cross_turn_accept_or_slice` | guard,binding | 3/3 (✓) | 100.0% | 19.35s | 83814/1681/29696 |
| `guard_no_silent_reuse_after_broad` | guard,binding | 2/3 (✓) | 66.67% | 21.39s | 153353/1243/64512 |
| `scope_class_chip` | scope | 0/3 (✗) | — | 61.93s | 282533/4249/125568 |
| `scope_week_range` | scope | 0/3 (✗) | — | 52.07s | 286439/5632/122496 |
| `scope_selected_students` | scope,scope-extended | 2/3 (✓) | — | 48.56s | 342382/3572/196416 |
| `scope_knowledge_attachment` | scope,scope-extended | 3/3 (✓) | — | 51.52s | 246464/4286/136576 |
| `scope_view_and_report_attachment` | scope,scope-extended | 1/3 (✗) | — | 26.11s | 117992/1612/91520 |
| `task_class_mean_score` | task,numeric | 0/3 (✗) | 0.0% | 58.28s | 347232/5057/137344 |
| `task_slice_count` | task,numeric,binding | 3/3 (✓) | 100.0% | 22.11s | 85091/2205/42624 |
| `task_two_step_query_agg` | task | 0/3 (✗) | 100.0% | 30.17s | 156224/2576/43776 |
| `task_list_bind_agg_chain` | task,binding,tools | 0/3 (✗) | 0.0% | 21.7s | 90980/1903/29440 |
| `task_enrich_score_rate_path` | task,tools | 0/3 (✗) | — | 27.56s | 155810/2435/57600 |
| `task_status_and_no_forbidden` | task,tools | 0/3 (✗) | 100.0% | 34.31s | 184372/2361/70528 |
| `tools_query_limit_10` | tools | 3/3 (✓) | — | 25.07s | 88287/2580/43392 |
| `tools_forbid_report_on_simple_query` | tools | 3/3 (✓) | — | 16.31s | 109720/1093/57344 |
| `tools_list_datasets_after_query` | tools | 1/3 (✗) | — | 14.18s | 54685/1523/31360 |
| `tools_enrich_then_aggregate` | tools | 0/3 (✗) | — | 32.21s | 176597/3162/66304 |
| `tools_inspect_schema_before_query` | tools | 3/3 (✓) | — | 22.05s | 66541/1724/40704 |
| `tools_query_with_class_filter` | tools | 3/3 (✓) | — | 62.06s | 316235/4690/153856 |
| `tools_aggregate_requires_metrics` | tools,task | 0/3 (✗) | 0.0% | 43.9s | 304684/4198/97152 |
| `tools_no_compact_on_short_task` | tools,efficiency | 3/3 (✓) | — | 16.59s | 63274/1517/38912 |

## 失败明细

| 场景 | run | metric | 原因 |
|------|-----|--------|------|
| `cross_turn_explicit_dataset` | 0 | `tool_correctness` | missing=['list_datasets'] |
| `cross_turn_explicit_dataset` | 2 | `tool_correctness` | missing=['list_datasets'] |
| `efficiency_query_agg_budget` | 0 | `binding_accuracy` | missing aggregate |
| `efficiency_query_agg_budget` | 0 | `tool_correctness` | missing=['query_data', 'aggregate_data'] |
| `efficiency_query_agg_budget` | 0 | `task_success` | no successful aggregate_data |
| `efficiency_query_agg_budget` | 0 | `task_success` | metric op=mean field=score not found |
| `efficiency_query_agg_budget` | 1 | `tool_correctness` | missing=['query_data'] |
| `efficiency_query_agg_budget` | 2 | `tool_correctness` | missing=['query_data'] |
| `efficiency_query_agg_budget` | 2 | `task_success` | metric op=mean field=score not found |
| `explicit_dataset_id_same_turn` | 0 | `binding_accuracy` | dataset_id mismatch meta='ds_022c17a99045' bound='ds_7e8015f7cee8' |
| `explicit_dataset_id_same_turn` | 0 | `tool_correctness` | missing=['query_data', 'list_datasets'] |
| `explicit_dataset_id_same_turn` | 1 | `binding_accuracy` | missing aggregate |
| `explicit_dataset_id_same_turn` | 1 | `tool_correctness` | missing=['list_datasets', 'aggregate_data'] |
| `explicit_dataset_id_same_turn` | 2 | `binding_accuracy` | missing aggregate |
| `explicit_dataset_id_same_turn` | 2 | `tool_correctness` | missing=['query_data', 'list_datasets', 'aggregate_data'] |
| `guard_consult_denies_query` | 0 | `guard_reject` | expected guard/permission error |
| `guard_no_silent_reuse_after_broad` | 2 | `binding_accuracy` | missing aggregate |
| `guard_reject_cross_turn_silent` | 0 | `binding_accuracy` | dataset user_turn=2 not prior to current=2 |
| `guard_reject_cross_turn_silent` | 1 | `binding_accuracy` | dataset user_turn=2 not prior to current=2 |
| `guard_reject_cross_turn_silent` | 2 | `binding_accuracy` | dataset user_turn=2 not prior to current=2 |
| `reject_cross_turn_silent` | 0 | `binding_accuracy` | dataset user_turn=2 not prior to current=2 |
| `reject_cross_turn_silent` | 1 | `binding_accuracy` | dataset user_turn=2 not prior to current=2 |
| `scope_class_chip` | 0 | `scope_contract` | missing:Class1 |
| `scope_class_chip` | 1 | `tool_correctness` | missing=['query_data'] |
| `scope_class_chip` | 1 | `arg_correctness` | no query_data call for args check |
| `scope_class_chip` | 1 | `scope_contract` | missing:Class1 |
| `scope_class_chip` | 2 | `scope_contract` | missing:Class1 |
| `scope_selected_students` | 2 | `tool_correctness` | missing=['get_current_filter_context'] |
| `scope_view_and_report_attachment` | 1 | `tool_correctness` | missing=['get_current_filter_context'] |
| `scope_view_and_report_attachment` | 2 | `tool_correctness` | missing=['get_current_filter_context'] |
| `scope_view_and_report_attachment` | 2 | `tool_correctness` | missing=['query_data'] |
| `scope_week_range` | 0 | `scope_contract` | missing:Class1 |
| `scope_week_range` | 1 | `scope_contract` | missing:Class1 |
| `scope_week_range` | 2 | `scope_contract` | missing:Class1 |
| `semantic_class_wide_single_turn` | 2 | `binding_accuracy` | missing aggregate |
| `semantic_class_wide_single_turn` | 2 | `task_success` | no successful aggregate_data |
| `semantic_class_wide_single_turn` | 2 | `task_success` | metric op=mean field=score not found |
| `single_turn_explicit_two_queries` | 0 | `binding_accuracy` | unexpected error: Error: 本回合尚无可用的 query 工作集，且禁止静默绑定上一轮 result_ref。跨轮续算：list_datasets → aggregate_data(input.dataset_id=…)。仅当教师要求新口径（不同班级/周次/条件）时才 query_data。
最近数据集（指代：看 grain/lab |
| `single_turn_explicit_two_queries` | 0 | `binding_accuracy` | unexpected error: Error: 本回合尚无可用的 query 工作集，且禁止静默绑定上一轮 result_ref。跨轮续算：list_datasets → aggregate_data(input.dataset_id=…)。仅当教师要求新口径（不同班级/周次/条件）时才 query_data。
最近数据集（指代：看 grain/lab |
| `single_turn_explicit_two_queries` | 0 | `tool_correctness` | missing=['query_data'] |
| `single_turn_explicit_two_queries` | 1 | `binding_accuracy` | unexpected error: Error: 本回合尚无可用的 query 工作集，且禁止静默绑定上一轮 result_ref。跨轮续算：list_datasets → aggregate_data(input.dataset_id=…)。仅当教师要求新口径（不同班级/周次/条件）时才 query_data。
最近数据集（指代：看 grain/lab |
| `single_turn_explicit_two_queries` | 1 | `binding_accuracy` | unexpected error: Error: 本回合尚无可用的 query 工作集，且禁止静默绑定上一轮 result_ref。跨轮续算：list_datasets → aggregate_data(input.dataset_id=…)。仅当教师要求新口径（不同班级/周次/条件）时才 query_data。
最近数据集（指代：看 grain/lab |
| `single_turn_explicit_two_queries` | 1 | `tool_correctness` | missing=['query_data'] |
| `single_turn_explicit_two_queries` | 2 | `binding_accuracy` | unexpected error: Error: dataset_id='ds_4d047b8748bc' 为全量（22960 行），但教师话要求切片/「这些记录」口径。请 list_datasets 后改选 limit 切片 dataset_id。
最近数据集（指代：看 grain/label；续算传 dataset_id；勿把「聚合表」当「原始行」） |
| `task_class_mean_score` | 0 | `binding_accuracy` | missing aggregate |
| `task_class_mean_score` | 0 | `task_success` | status=failed |
| `task_class_mean_score` | 0 | `task_success` | no successful aggregate_data |
| `task_class_mean_score` | 0 | `task_success` | metric op=mean field=score not found |
| `task_class_mean_score` | 0 | `task_success` | no tool result |
| `task_class_mean_score` | 1 | `binding_accuracy` | missing aggregate |
| `task_class_mean_score` | 1 | `task_success` | status=failed |
| `task_class_mean_score` | 1 | `task_success` | no successful aggregate_data |
| `task_class_mean_score` | 1 | `task_success` | metric op=mean field=score not found |
| `task_class_mean_score` | 1 | `task_success` | no tool result |
| `task_class_mean_score` | 2 | `binding_accuracy` | missing aggregate |
| `task_class_mean_score` | 2 | `task_success` | status=failed |
| `task_class_mean_score` | 2 | `task_success` | no successful aggregate_data |
| `task_class_mean_score` | 2 | `task_success` | metric op=mean field=score not found |
| `task_class_mean_score` | 2 | `task_success` | no tool result |
| `task_enrich_score_rate_path` | 0 | `tool_correctness` | missing=['query_data', 'enrich_data'] |
| `task_enrich_score_rate_path` | 0 | `task_success` | no successful enrich_data |
| `task_enrich_score_rate_path` | 1 | `tool_correctness` | missing=['query_data', 'enrich_data'] |
| `task_enrich_score_rate_path` | 1 | `task_success` | no successful enrich_data |
| `task_enrich_score_rate_path` | 2 | `tool_correctness` | missing=['query_data', 'enrich_data'] |
| `task_enrich_score_rate_path` | 2 | `task_success` | no successful enrich_data |
| `task_list_bind_agg_chain` | 0 | `binding_accuracy` | missing aggregate |
| `task_list_bind_agg_chain` | 0 | `tool_correctness` | missing=['list_datasets', 'aggregate_data'] |
| `task_list_bind_agg_chain` | 0 | `task_success` | tool not called: list_datasets |
| `task_list_bind_agg_chain` | 0 | `task_success` | no successful aggregate_data |
| `task_list_bind_agg_chain` | 1 | `binding_accuracy` | missing aggregate |
| `task_list_bind_agg_chain` | 1 | `tool_correctness` | missing=['list_datasets', 'aggregate_data'] |
| `task_list_bind_agg_chain` | 1 | `task_success` | tool not called: list_datasets |
| `task_list_bind_agg_chain` | 1 | `task_success` | no successful aggregate_data |
| `task_list_bind_agg_chain` | 2 | `binding_accuracy` | missing aggregate |
| `task_list_bind_agg_chain` | 2 | `tool_correctness` | missing=['list_datasets', 'aggregate_data'] |
| `task_list_bind_agg_chain` | 2 | `task_success` | tool not called: list_datasets |
| `task_list_bind_agg_chain` | 2 | `task_success` | no successful aggregate_data |
| `task_status_and_no_forbidden` | 0 | `task_success` | status=failed |
| `task_status_and_no_forbidden` | 1 | `task_success` | status=failed |
| `task_status_and_no_forbidden` | 2 | `task_success` | status=failed |
| … | … | … | 另有 34 条 |

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
