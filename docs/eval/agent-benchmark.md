# Agent Benchmark Harness

通用在线评测：一套 Runner + 可插拔 Metrics。同一场景跑一遍，同时产出正确性（P0）与效率（P2）指标。

## 输出与防重跑（默认开启）

| 文件 | 内容 |
|------|------|
| `data/eval/agent_benchmark.json` | 最终汇总 + 全量 `runs[]` |
| `data/eval/agent_benchmark.partial.jsonl` | **增量 checkpoint**（每跑完一条 append 一行） |
| `data/eval/agent_benchmark.manifest.json` | model / git / scenario 指纹 / Langfuse 筛选 hint |
| `docs/eval/agent-benchmark-report.md` | 人类可读摘要 |

默认行为：

- **checkpoint 开启**（`--no-checkpoint` 可关）
- **失败 session 保留**（`--keep-session on-failure`，成功 run 仍清理）
- Langfuse turn metadata 含 `benchmark_run_id`，便于按 run 筛账单

中断后：用 `agent_benchmark.partial.jsonl` 里已完成的 `trace` 恢复分析，不必重跑已完成 session。

## 快速开始

```bash
# 冒烟（无 API，校验 schema / dry-run）
python backend/agent/eval/run_agent_benchmark.py --dry-run --runs 1

# 日常回归（默认）
python backend/agent/eval/run_agent_benchmark.py --runs 3

# 发版基线
python backend/agent/eval/run_agent_benchmark.py --runs 8

# 按 tag / 单场景
python backend/agent/eval/run_agent_benchmark.py --tags binding --runs 1
python backend/agent/eval/run_agent_benchmark.py --scenario chain_slice_two_turns --runs 1
```

输出：

- JSON：`data/eval/agent_benchmark.json`
- Markdown：`docs/eval/agent-benchmark-report.md`

## 架构

```
Scenario JSON → Runner (SessionManager + AgentLoop)
             → RunTrace (turns / tools / usage / duration)
             → Metrics plugins
             → Report (正确性表 + 效率表 + 失败明细)
```

| 模块 | 路径 |
|------|------|
| CLI | `backend/agent/eval/run_agent_benchmark.py` |
| Runner | `backend/agent/eval/runner.py` |
| Trace | `backend/agent/eval/trace.py` |
| Schema | `backend/agent/eval/schema.py` |
| Metrics | `backend/agent/eval/metrics/` |
| Fixtures | `backend/agent/eval/fixtures/scenarios/*.json` |

离线 binding 快门禁仍用：`backend/agent/eval/binding_accuracy.py`（`BINDING_RESOLVER_DISABLE_LLM=1`）。

## Metrics

### P0（硬门禁）

| Metric | 说明 |
|--------|------|
| `binding_accuracy` | 复用 `binding_judge`；按 aggregate 判定 |
| `tool_correctness` / `forbid_tools` | expect_tools / forbid_tools |
| `arg_correctness` | 字段级参数断言 |
| `scope_contract` | ui_scope / 附件是否注入并遵守 |
| `guard_reject` | 跨 turn reject / mode deny |
| `task_success` | 声明式最终断言 |

### P1

| Metric | 说明 |
|--------|------|
| `step_efficiency` | expect_max_tool_calls / turns |
| `loop_health` | timeout、缺工具、oscillation、compact 滥用 |
| `failure_tags` | 归因标签（诊断用） |

### P2（同报告，默认非硬门禁）

| Metric | 说明 |
|--------|------|
| `latency` | 端到端 + per-turn |
| `tokens_cost` | input/output/cached + 估算 USD |
| `cache_hit_rate` | cached / input |

效率优先在**成功 run**上取 median。主正确性：pass@1 + pass@k；binding 继续按 aggregate 判定数。

## 场景契约（摘要）

**教师话术**写在 `turns` 里（自然中文，约 3 轮）；**判定逻辑**写在 `expect_*` 里（机器可读，勿混进 turns）。

```json
{
  "id": "example",
  "tags": ["binding", "tools"],
  "mode": "analyze",
  "filter_context": {"classes": ["Class1"]},
  "ui_scope": {"classes": ["Class1"]},
  "turns": [
    "Class1 这次作业，我想先看得分最低的 10 条。",
    "就这 10 条，帮我算一下平均分和条数。",
    "请一定按刚才那 10 条来算，别换成全班。"
  ],
  "expect_aggregates": [{"turn_index": 0, "expect": "slice"}],
  "expect_tools": [{"names": ["query_data", "aggregate_data"]}],
  "forbid_tools": ["write_report"],
  "expect_args": [{"tool": "query_data", "path": "limit", "eq": 10}],
  "expect_task": {"asserts": [{"kind": "aggregate_has_metric", "metric_op": "mean", "field": "score"}]},
  "expect_scope": {"must_contain": ["Class1"]},
  "expect_error": false,
  "expect_max_tool_calls": 6,
  "expect_max_turns": 2
}
```

硬约束：单场景 **3 轮左右**（上限 3 turns）；`turns` 文案须为**教师自然语言**（非 query/aggregate 等开发术语）；v1 约 37 scenarios。

### 场景桶（v1）

| 文件 | 桶 | 约略数量 |
|------|----|----------|
| `binding.json` | Binding / 数据链 | 12 |
| `tools.json` | 工具选择与参数 | 8 |
| `scope.json` | Scope / 附件 | 5 |
| `guard.json` | Guard / 权限 | 4 |
| `task.json` | 任务成功 | 6 |
| `efficiency.json` | 效率探针 | 2 |

## 如何加场景

1. 在对应 `fixtures/scenarios/*.json` 追加一条（或新建 tag 文件）。
2. `--dry-run` 确认 schema 与 synthetic 判定通过。
3. 有 API 时用 `--scenario <id> --runs 1` 冒烟，再 `--runs 3` 看稳定性。

## 运行协议

| 用途 | `--runs` |
|------|----------|
| 冒烟 | 1 |
| 日常回归（默认） | 3 |
| 发版 / 基线 | 8–10 |
| Flaky 专项 | 仅对不稳定子集 10–30 |

`--pass-strategy`：`majority`（默认）/ `any_pass` / `all_pass`。

## Pytest

```bash
pytest backend/agent/test/test_agent_benchmark.py -q

# 在线集成（需 API Key）
$env:RUN_AGENT_ONLINE=1
pytest backend/agent/test/test_agent_benchmark.py -m integration
```

## 与旧 binding online eval

本 harness 提拔自 `run_binding_online_eval.py` 的 SessionManager + AgentLoop 脚手架；binding 降为第一个 Metric 插件。请优先使用本 CLI；离线 `binding_accuracy.py` 仍作快门禁。
