"""Unified JSON + Markdown report for agent benchmark."""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from eval.schema import Scenario
from eval.trace import RunTrace


def _pct(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    return round(s[max(0, int(len(s) * p) - 1)], 2)


def _hard_passed(trace: RunTrace) -> bool:
    hard = [m for m in trace.metric_results if m.get("hard_gate", True)]
    if not hard:
        return trace.status == "ok"
    return all(m.get("passed") for m in hard) and trace.status in ("ok", "failed")


def _metric_rows(traces: list[RunTrace]) -> list[dict[str, Any]]:
    rows = []
    for tr in traces:
        for m in tr.metric_results:
            rows.append(
                {
                    "scenario_id": tr.scenario_id,
                    "run_index": tr.run_index,
                    "metric": m.get("name"),
                    "passed": m.get("passed"),
                    "score": m.get("score"),
                    "detail": m.get("detail"),
                    "hard_gate": m.get("hard_gate", True),
                    "tags": m.get("tags") or [],
                    "evidence": m.get("evidence") or {},
                }
            )
    return rows


def summarize(
    traces: list[RunTrace],
    *,
    scenarios: list[Scenario],
    runs_per_scenario: int,
    pass_strategy: str = "majority",
    manifest: dict[str, Any] | None = None,
    finished_at: str | None = None,
) -> dict[str, Any]:
    """Aggregate traces into a report summary.

    pass_strategy: any_pass | majority | all_pass — how to collapse multi-run scenario success.
    """
    by_scenario: dict[str, list[RunTrace]] = defaultdict(list)
    for tr in traces:
        by_scenario[tr.scenario_id].append(tr)

    scenario_rows = []
    pass_at_1 = 0
    pass_at_k = 0
    for sc in scenarios:
        runs = by_scenario.get(sc.id, [])
        hard_flags = [_hard_passed(tr) for tr in runs]
        n = len(hard_flags)
        n_pass = sum(1 for x in hard_flags if x)
        if pass_strategy == "any_pass":
            scen_ok = n_pass >= 1
        elif pass_strategy == "all_pass":
            scen_ok = n > 0 and n_pass == n
        else:  # majority
            scen_ok = n > 0 and n_pass * 2 > n

        if n_pass >= 1:
            pass_at_k += 1
        if hard_flags and hard_flags[0]:
            pass_at_1 += 1

        # Binding sub-accuracy
        bind = [
            m
            for tr in runs
            for m in tr.metric_results
            if m.get("name") == "binding_accuracy"
        ]
        bind_ok = sum(1 for m in bind if m.get("passed"))
        bind_total = len(bind)

        success_runs = [tr for tr, ok in zip(runs, hard_flags) if ok]
        eff_pool = success_runs or runs
        durations = [tr.duration_sec for tr in eff_pool if tr.duration_sec]
        inputs = [tr.usage.input_tokens for tr in eff_pool]
        outputs = [tr.usage.output_tokens for tr in eff_pool]
        cached = [tr.usage.cached_tokens for tr in eff_pool]
        cache_rates = [
            tr.usage.cache_hit_rate for tr in eff_pool if tr.usage.cache_hit_rate is not None
        ]

        scenario_rows.append(
            {
                "id": sc.id,
                "tags": sc.tags,
                "runs": n,
                "hard_pass_runs": n_pass,
                "scenario_pass": scen_ok,
                "pass_rate": round(100 * n_pass / n, 2) if n else 0.0,
                "binding_accuracy_pct": (
                    round(100 * bind_ok / bind_total, 2) if bind_total else None
                ),
                "binding_correct": bind_ok,
                "binding_total": bind_total,
                "median_duration_sec": (
                    round(statistics.median(durations), 2) if durations else None
                ),
                "median_input_tokens": int(statistics.median(inputs)) if inputs else None,
                "median_output_tokens": int(statistics.median(outputs)) if outputs else None,
                "median_cached_tokens": int(statistics.median(cached)) if cached else None,
                "median_cache_hit_rate": (
                    round(statistics.median(cache_rates), 4) if cache_rates else None
                ),
                "failure_tags": sorted(
                    {t for tr in runs for t in tr.failure_tags}
                ),
            }
        )

    # Global binding
    all_bind = [
        m
        for tr in traces
        for m in tr.metric_results
        if m.get("name") == "binding_accuracy"
    ]
    bind_ok = sum(1 for m in all_bind if m.get("passed"))
    bind_total = len(all_bind)

    # Hard gate metric pass rates
    by_metric: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "passed": 0})
    for m in _metric_rows(traces):
        name = str(m["metric"])
        by_metric[name]["total"] += 1
        if m["passed"]:
            by_metric[name]["passed"] += 1

    metric_summary = {
        name: {
            "total": v["total"],
            "passed": v["passed"],
            "pct": round(100 * v["passed"] / v["total"], 2) if v["total"] else 0.0,
        }
        for name, v in sorted(by_metric.items())
    }

    # Efficiency on successful runs + all runs
    # duration_sec = whole scenario wall clock (usually all turns);
    # turn_durations_sec = per user-turn wall clock (preferred UX latency).
    success_traces = [tr for tr in traces if _hard_passed(tr)]
    pool = success_traces or traces
    durations = [tr.duration_sec for tr in pool]
    all_durations = [tr.duration_sec for tr in traces if tr.duration_sec]
    all_turns: list[float] = []
    for tr in traces:
        all_turns.extend(float(x) for x in (tr.turn_durations_sec or []) if x is not None)
    success_turns: list[float] = []
    for tr in success_traces:
        success_turns.extend(
            float(x) for x in (tr.turn_durations_sec or []) if x is not None
        )

    def _est_usd(tr: RunTrace) -> float:
        for m in tr.metric_results:
            if m.get("name") == "tokens_cost":
                est = (m.get("evidence") or {}).get("est_usd")
                if est is not None:
                    return float(est)
        u = tr.usage
        cached = min(int(u.cached_tokens or 0), int(u.input_tokens or 0))
        # DeepSeek V4 Flash list (USD / 1M) — same defaults as metrics.cost
        return (
            (u.input_tokens - cached) / 1e6 * 0.14
            + cached / 1e6 * 0.0028
            + u.output_tokens / 1e6 * 0.28
        )

    cost_usd = [_est_usd(tr) for tr in success_traces] if success_traces else []
    all_cost_usd = [_est_usd(tr) for tr in traces]
    tin = sum(int(tr.usage.input_tokens or 0) for tr in traces)
    tout = sum(int(tr.usage.output_tokens or 0) for tr in traces)
    tcached = sum(int(tr.usage.cached_tokens or 0) for tr in traces)
    calls = sum(int(tr.usage.llm_calls or 0) for tr in traces)

    failures = []
    for tr in traces:
        for m in tr.metric_results:
            if m.get("hard_gate", True) and not m.get("passed"):
                failures.append(
                    {
                        "scenario_id": tr.scenario_id,
                        "run_index": tr.run_index,
                        "metric": m.get("name"),
                        "detail": m.get("detail"),
                        "status": tr.status,
                        "evidence": m.get("evidence"),
                    }
                )
        if tr.status in ("timeout", "error", "skipped") and tr.error:
            failures.append(
                {
                    "scenario_id": tr.scenario_id,
                    "run_index": tr.run_index,
                    "metric": "run_status",
                    "detail": tr.error,
                    "status": tr.status,
                }
            )

    n_scen = len(scenarios)
    out: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": finished_at or datetime.now(timezone.utc).isoformat(),
        "manifest": manifest,
        "N_scenarios": n_scen,
        "N_runs_per_scenario": runs_per_scenario,
        "N_session_runs": len(traces),
        "pass_strategy": pass_strategy,
        "pass_at_1": pass_at_1,
        "pass_at_1_pct": round(100 * pass_at_1 / n_scen, 2) if n_scen else 0.0,
        "pass_at_k": pass_at_k,
        "pass_at_k_pct": round(100 * pass_at_k / n_scen, 2) if n_scen else 0.0,
        "binding_accuracy_pct": round(100 * bind_ok / bind_total, 2) if bind_total else None,
        "binding_correct": bind_ok,
        "binding_total": bind_total,
        "metrics": metric_summary,
        "scenarios": scenario_rows,
        "efficiency": {
            "latency_unit_note": (
                "turn_* = single user turn wall clock; "
                "scenario_* / *_duration_sec_* without turn_ = full scenario "
                "(typically 3 turns summed)"
            ),
            "median_turn_duration_sec_all": (
                round(statistics.median(all_turns), 2) if all_turns else None
            ),
            "p95_turn_duration_sec_all": _pct(all_turns, 0.95),
            "mean_turn_duration_sec_all": (
                round(statistics.mean(all_turns), 2) if all_turns else None
            ),
            "n_turns_all": len(all_turns),
            "median_turn_duration_sec_success": (
                round(statistics.median(success_turns), 2) if success_turns else None
            ),
            "p95_turn_duration_sec_success": _pct(success_turns, 0.95),
            "median_duration_sec_success": (
                round(statistics.median(durations), 2) if durations else None
            ),
            "p95_duration_sec_success": (
                round(sorted(durations)[max(0, int(len(durations) * 0.95) - 1)], 2)
                if durations
                else None
            ),
            "median_duration_sec_all": (
                round(statistics.median(all_durations), 2) if all_durations else None
            ),
            "p95_duration_sec_all": (
                round(sorted(all_durations)[max(0, int(len(all_durations) * 0.95) - 1)], 2)
                if all_durations
                else None
            ),
            "mean_duration_sec_all": (
                round(statistics.mean(all_durations), 2) if all_durations else None
            ),
            "n_duration_all": len(all_durations),
            "pricing": {
                "model": "deepseek-v4-flash",
                "usd_per_1m": {"cache_miss": 0.14, "cache_hit": 0.0028, "output": 0.28},
            },
            "total_est_usd_all": (
                round(sum(all_cost_usd), 4) if all_cost_usd else None
            ),
            "median_est_usd_all": (
                round(statistics.median(all_cost_usd), 6) if all_cost_usd else None
            ),
            "mean_est_usd_all": (
                round(statistics.mean(all_cost_usd), 6) if all_cost_usd else None
            ),
            "p95_est_usd_all": (
                round(
                    sorted(all_cost_usd)[max(0, int(len(all_cost_usd) * 0.95) - 1)],
                    6,
                )
                if all_cost_usd
                else None
            ),
            "total_est_usd_success": (
                round(sum(cost_usd), 4) if cost_usd else None
            ),
            "median_est_usd_success": (
                round(statistics.median(cost_usd), 6) if cost_usd else None
            ),
            "cost_per_successful_task": (
                round(statistics.median(cost_usd), 6) if cost_usd else None
            ),
            "success_runs": len(success_traces),
            "tokens_total": {
                "input": tin,
                "output": tout,
                "cached": tcached,
                "llm_calls": calls,
                "cache_hit_rate": round(tcached / tin, 4) if tin else None,
            },
        },
        "failures": failures,
        "runs": [tr.to_dict() for tr in traces],
    }
    return out


def render_markdown(summary: dict[str, Any]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    manifest = summary.get("manifest") or {}
    manifest_lines = ["| 字段 | 值 |", "|------|-----|"]
    if manifest:
        manifest_lines.append(f"| benchmark_run_id | `{manifest.get('benchmark_run_id')}` |")
        prov = manifest.get("provider") or {}
        manifest_lines.append(f"| model | `{prov.get('model')}` |")
        manifest_lines.append(f"| base_url | `{prov.get('base_url')}` |")
        git = manifest.get("git") or {}
        manifest_lines.append(f"| git commit | `{git.get('commit')}` |")
        manifest_lines.append(f"| scenario fingerprint | `{manifest.get('scenario_fingerprint')}` |")
        outs = manifest.get("outputs") or {}
        manifest_lines.append(f"| checkpoint | `{outs.get('checkpoint_jsonl')}` |")
        lf = manifest.get("langfuse") or {}
        hint = lf.get("filter_hint") or {}
        meta = hint.get("metadata") or {}
        manifest_lines.append(
            f"| Langfuse 筛选 | session `{hint.get('session_id_prefix')}*` + "
            f"`benchmark_run_id={meta.get('benchmark_run_id')}` |"
        )
    else:
        manifest_lines.append("| — | — |")

    scen_lines = [
        "| 场景 | tags | pass | binding | median latency | median tokens (in/out/cache) |",
        "|------|------|------|---------|----------------|------------------------------|",
    ]
    for s in summary.get("scenarios") or []:
        bind = (
            f"{s.get('binding_accuracy_pct')}%"
            if s.get("binding_accuracy_pct") is not None
            else "—"
        )
        toks = (
            f"{s.get('median_input_tokens')}/{s.get('median_output_tokens')}/{s.get('median_cached_tokens')}"
            if s.get("median_input_tokens") is not None
            else "—"
        )
        tags = ",".join(s.get("tags") or [])
        scen_lines.append(
            f"| `{s['id']}` | {tags} | {s.get('hard_pass_runs')}/{s.get('runs')} "
            f"({'✓' if s.get('scenario_pass') else '✗'}) | {bind} | "
            f"{s.get('median_duration_sec')}s | {toks} |"
        )

    metric_lines = ["| Metric | passed/total | pct |", "|--------|--------------|-----|"]
    for name, v in (summary.get("metrics") or {}).items():
        metric_lines.append(f"| `{name}` | {v['passed']}/{v['total']} | {v['pct']}% |")

    fail_lines = ["| 场景 | run | metric | 原因 |", "|------|-----|--------|------|"]
    fails = summary.get("failures") or []
    if not fails:
        fail_lines.append("| — | — | — | 无 |")
    else:
        for f in fails[:80]:
            fail_lines.append(
                f"| `{f.get('scenario_id')}` | {f.get('run_index')} | "
                f"`{f.get('metric')}` | {f.get('detail')} |"
            )
        if len(fails) > 80:
            fail_lines.append(f"| … | … | … | 另有 {len(fails) - 80} 条 |")

    eff = summary.get("efficiency") or {}
    return f"""# Agent Benchmark 报告

> 生成时间：{now}  
> 脚本：`backend/agent/eval/run_agent_benchmark.py`

## 运行清单（manifest）

{chr(10).join(manifest_lines)}

## 汇总

| 指标 | 值 |
|------|-----|
| 场景数 N_scenarios | {summary.get("N_scenarios")} |
| runs / scenario | {summary.get("N_runs_per_scenario")} |
| session-runs | {summary.get("N_session_runs")} |
| pass 策略 | {summary.get("pass_strategy")} |
| **pass@1** | **{summary.get("pass_at_1_pct")}%** ({summary.get("pass_at_1")}/{summary.get("N_scenarios")}) |
| **pass@k** (≥1 run 过硬门禁) | **{summary.get("pass_at_k_pct")}%** ({summary.get("pass_at_k")}/{summary.get("N_scenarios")}) |
| Binding accuracy (aggregate 判定) | {summary.get("binding_accuracy_pct")}% ({summary.get("binding_correct")}/{summary.get("binding_total")}) |
| **单 turn 中位延迟（推荐）** | {eff.get("median_turn_duration_sec_all", "—")}s |
| **单 turn p95 延迟** | {eff.get("p95_turn_duration_sec_all", "—")}s |
| 单 turn 样本数 | {eff.get("n_turns_all", "—")} |
| 整场景中位延迟（通常 3 turns 合计） | {eff.get("median_duration_sec_all", "—")}s |
| 整场景 p95 延迟 | {eff.get("p95_duration_sec_all", "—")}s |
| 成功 run 整场景中位 | {eff.get("median_duration_sec_success")}s |
| 成功 run 整场景 p95 | {eff.get("p95_duration_sec_success")}s |
| 全部 run 估算总成本 | ${eff.get("total_est_usd_all", "—")} |
| 全部 run 中位成本 | ${eff.get("median_est_usd_all", "—")} |
| 全部 run p95 成本 | ${eff.get("p95_est_usd_all", "—")} |
| cost_per_successful_task (估) | ${eff.get("cost_per_successful_task")} |

## Metrics

{chr(10).join(metric_lines)}

## 按场景（正确性 + 效率）

{chr(10).join(scen_lines)}

## 失败明细

{chr(10).join(fail_lines)}

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
"""
