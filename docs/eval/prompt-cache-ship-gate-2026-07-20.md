# Prompt Cache 上线闸门记录

> 生成时间：2026-07-20  
> 分支：`feat/prompt-cache-opt`（dirty，相对 `88ae102`）  
> 本跑：`20260720T140335Z-c7ae60f0`  
> 对照基线：`20260720T123049Z-bf4e95bd`（优化前合并全量）

## 跑法

```bash
py -3.11 backend/agent/eval/run_agent_benchmark.py --runs 3 \
  --tags "binding,efficiency,guard,numeric,scope,scope-extended,task,tools"
```

- 37 场景 × 3 runs = **111 session-runs**
- 模型：`deepseek-v4-flash`
- 报告：`data/eval/runs/20260720T140335Z-c7ae60f0/report.md`

## 总览对照

| 指标 | 基线 (bf4e95bd) | 本跑 (cache-opt) | 变化 |
|------|-----------------|------------------|------|
| pass@1 | 51.35% (19/37) | **59.46% (22/37)** | +8.1 pp |
| pass@k | 62.16% (23/37) | **67.57% (25/37)** | +5.4 pp |
| binding_accuracy | 61.11% (44/72) | **66.67% (48/72)** | +5.6 pp |
| scope_contract | 0.0% (0/15) | **93.33% (14/15)** | 大修复 |
| loop_health | 5.41% (6/111) | **56.76% (63/111)** | 大修复 |
| tool_correctness | 56.79% | **61.73%** | +4.9 pp |
| task_success | 41.27% | **60.32%** | +19 pp |
| 单 turn 中位延迟 | 8.31s | 8.11s | ≈持平 |
| 整场景中位延迟 | 26.11s | 25.54s | ≈持平 |
| 全部 run 估费 | **$1.6157** | **$0.3494** | **−78.4%** |
| cost_per_successful_task | $0.008345 | $0.00242 | −71% |
| cache hit（全量 tokens） | （基线约 ~47% 量级） | **92.09%** | 显著升高 |

本跑 tokens 合计：input 19,301,355 / cached 17,774,464 / output 306,738。  
若无 cache 按 miss 全价估约 **$2.79**；实际 **$0.35**，相对「无 cache」约省 **87.5%**。

## Cache / 成本结论

- 全量 111 runs 平均 **cache hit ≈ 92%**，账单约为优化前同规模的 **~1/5**。
- 正确性指标相对基线 **未回退**；pass@1 / binding / scope / task 均有提升（scope_contract 从接近全挂到 93%）。

## 仍失败的场景（majority 未过，13 个）

多为既有 binding / task / tools 能力问题，失败原因以缺 `list_datasets`、binding broad/slice、缺 aggregate 为主，**未见「system 冻住导致完全失忆」类集中回归**。

| 场景 | pass_rate | 标签 |
|------|-----------|------|
| single_turn_explicit_two_queries | 0% | binding,tools |
| cross_turn_explicit_dataset | 0% | binding,tools |
| semantic_class_wide_single_turn | 0% | binding,task |
| reject_cross_turn_silent | 33% | binding,guard |
| explicit_dataset_id_same_turn | 0% | binding,tools |
| two_turn_list_then_explicit_bind | 0% | binding,tools |
| scope_view_and_report_attachment | 0% | scope,scope-extended |
| task_class_mean_score | 0% | task,numeric |
| task_two_step_query_agg | 0% | task |
| task_list_bind_agg_chain | 0% | task,binding,tools |
| task_enrich_score_rate_path | 0% | task,tools |
| tools_enrich_then_aggregate | 0% | tools |
| tools_aggregate_requires_metrics | 0% | tools,task |

Scope 主路径：`scope_class_chip` / `scope_week_range` 3/3 过；`scope_selected_students` / `scope_knowledge_attachment` 2/3 过。

## 上线建议

**可以合并上线（主线默认）**，依据：

1. 正确性相对优化前基线不降反升  
2. 成本大幅下降（同规模约 −78%）  
3. cache hit 稳定在 ~90%+  

建议上线后：

- 保留 3–7 天账单与错误日志观察  
- 未过的 13 场景按 binding/task  backlog 跟进，**不必挡本次 cache PR**  
- 可选：`AGENT_PROMPT_CACHE_STABLE=0` 回滚开关（若尚未加，可作为 follow-up）

## 产物路径

- 报告：`data/eval/runs/20260720T140335Z-c7ae60f0/report.md`
- JSON：`data/eval/runs/20260720T140335Z-c7ae60f0/agent_benchmark.json`
- Manifest：同目录 `manifest.json`
