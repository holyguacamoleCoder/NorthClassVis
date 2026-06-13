#!/usr/bin/env python3
"""Offline dataset binding accuracy evaluation for aggregate_data.

Measures whether resolve_aggregate_binding picks the expected result_ref
(or correctly rejects with Error for guard cases).

Usage (repo root):
    python backend/agent/eval/binding_accuracy.py
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import runtime_bootstrap  # noqa: F401

# Deterministic semantic path: rules + heuristic (no live LLM).
os.environ.setdefault("BINDING_RESOLVER_DISABLE_LLM", "1")

from common.paths import AGENT_STATE_DIR  # noqa: E402
from data.dataset_registry import DatasetRecord, append_dataset  # noqa: E402
from loop_state import AnalysisToolContext, QuerySnapshot  # noqa: E402
from tools.runtime.binding.pipeline import resolve_aggregate_binding  # noqa: E402
from tools.runtime.binding.types import BindMode  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_JSON = REPO_ROOT / "data" / "eval" / "binding_accuracy.json"
DEFAULT_REPORT = REPO_ROOT / "docs" / "eval" / "binding-accuracy.md"
EVAL_SESSION_PREFIX = "binding-eval-"


@dataclass
class Scenario:
    id: str
    category: str
    teacher_message: str = ""
    user_turn: int = 1
    input: dict[str, Any] = field(default_factory=dict)
    metrics: list[dict[str, Any]] = field(default_factory=list)
    bind: str = "auto"
    snapshots: list[dict[str, Any]] = field(default_factory=list)
    batch: list[str] | None = None  # result_ref keys into snapshots
    prior_datasets: list[dict[str, Any]] = field(default_factory=list)
    expect_result_ref: str | None = None
    expect_dataset_id: str | None = None
    expect_error: bool = False
    expect_error_contains: str | None = None


def _snap(d: dict[str, Any]) -> QuerySnapshot:
    return QuerySnapshot(
        result_ref=str(d["result_ref"]),
        result_rows=int(d.get("result_rows", 0)),
        query_limit=d.get("query_limit"),
        rows_scanned=d.get("rows_scanned"),
        resource=d.get("resource"),
        dataset_id=d.get("dataset_id"),
    )


SLICE = {
    "result_ref": "query-results/slice10.json",
    "result_rows": 10,
    "query_limit": 10,
    "rows_scanned": 22960,
    "dataset_id": "ds_slice",
    "resource": "submit_record",
}
BROAD = {
    "result_ref": "query-results/full.json",
    "result_rows": 22960,
    "rows_scanned": 22960,
    "dataset_id": "ds_full",
    "resource": "submit_record",
}
MID = {
    "result_ref": "query-results/mid100.json",
    "result_rows": 100,
    "query_limit": 100,
    "rows_scanned": 22960,
    "dataset_id": "ds_mid",
    "resource": "submit_record",
}


def build_scenarios() -> list[Scenario]:
    return [
        Scenario(
            id="single_auto_input",
            category="rule_single",
            snapshots=[BROAD],
            metrics=[{"op": "count", "as": "n"}],
            expect_result_ref=BROAD["result_ref"],
        ),
        Scenario(
            id="single_explicit_ref_match",
            category="rule_single",
            snapshots=[BROAD],
            input={"result_ref": BROAD["result_ref"]},
            metrics=[{"op": "mean", "field": "score", "as": "avg"}],
            expect_result_ref=BROAD["result_ref"],
        ),
        Scenario(
            id="explicit_dataset_id",
            category="explicit",
            snapshots=[SLICE],
            prior_datasets=[
                {
                    "dataset_id": "ds_slice",
                    "result_ref": SLICE["result_ref"],
                    "user_turn": 1,
                    "result_rows": 10,
                    "query_limit": 10,
                }
            ],
            input={"dataset_id": "ds_slice"},
            metrics=[{"op": "count", "as": "n"}],
            bind="chain",
            expect_result_ref=SLICE["result_ref"],
            expect_dataset_id="ds_slice",
        ),
        Scenario(
            id="chain_from_dataset_id",
            category="explicit",
            prior_datasets=[
                {
                    "dataset_id": "ds_chain",
                    "result_ref": SLICE["result_ref"],
                    "user_turn": 1,
                    "result_rows": 10,
                    "query_limit": 10,
                }
            ],
            input={"chain_from_dataset_id": "ds_chain"},
            metrics=[{"op": "mean", "field": "score", "as": "avg"}],
            expect_result_ref=SLICE["result_ref"],
            expect_dataset_id="ds_chain",
        ),
        Scenario(
            id="bind_chain_prefers_slice",
            category="rule_bind",
            snapshots=[SLICE, BROAD],
            batch=["slice10", "full"],
            input={"result_ref": BROAD["result_ref"]},
            metrics=[{"op": "count", "as": "n"}],
            bind="chain",
            expect_result_ref=SLICE["result_ref"],
        ),
        Scenario(
            id="bind_fresh_prefers_broad",
            category="rule_bind",
            teacher_message="用 Class1 全班全量数据统计整体规模",
            snapshots=[SLICE, BROAD],
            metrics=[{"op": "count_distinct", "field": "student_ID", "as": "n"}],
            bind="fresh",
            expect_result_ref=BROAD["result_ref"],
        ),
        Scenario(
            id="auto_no_input_picks_broad_for_class_metric",
            category="rule_scoring",
            teacher_message="这个班整体有多少学生",
            snapshots=[SLICE, BROAD],
            metrics=[{"op": "count_distinct", "field": "student_ID", "as": "students"}],
            bind="auto",
            expect_result_ref=BROAD["result_ref"],
        ),
        Scenario(
            id="auto_no_input_picks_slice_for_chain_metric",
            category="rule_scoring",
            snapshots=[SLICE, BROAD],
            metrics=[{"op": "count", "as": "n"}, {"op": "mean", "field": "score", "as": "avg"}],
            bind="auto",
            expect_result_ref=SLICE["result_ref"],
        ),
        Scenario(
            id="semantic_chain_corrects_wrong_broad_ref",
            category="semantic_heuristic",
            teacher_message=(
                "先找出 Class1 得分最低的前 10 条提交，"
                "再汇总这些记录的分数分布（条数、均值）。"
            ),
            snapshots=[SLICE, BROAD],
            batch=["slice10", "full"],
            input={"result_ref": BROAD["result_ref"]},
            metrics=[
                {"op": "count", "field": "score", "as": "n"},
                {"op": "mean", "field": "score", "as": "avg"},
            ],
            bind="auto",
            expect_result_ref=SLICE["result_ref"],
        ),
        Scenario(
            id="semantic_class_wide_keeps_broad",
            category="semantic_heuristic",
            teacher_message="用 Class1 的数据，说一下这个班提交的整体情况：规模、分数水平、偏科知识点。",
            snapshots=[BROAD],
            input={"result_ref": BROAD["result_ref"]},
            metrics=[
                {"op": "count_distinct", "field": "student_ID", "as": "students"},
                {"op": "mean", "field": "score", "as": "avg"},
            ],
            bind="auto",
            expect_result_ref=BROAD["result_ref"],
        ),
        Scenario(
            id="semantic_these_records_with_only_slice",
            category="semantic_heuristic",
            teacher_message="汇总这些记录的条数和平均分",
            snapshots=[SLICE],
            input={"result_ref": SLICE["result_ref"]},
            metrics=[{"op": "count", "as": "n"}],
            bind="auto",
            expect_result_ref=SLICE["result_ref"],
        ),
        Scenario(
            id="explicit_ref_step1_slice_numbered",
            category="semantic_heuristic",
            teacher_message=(
                "请对 Class1 依次完成：1) query limit=10；2) query 全量；"
                "3) aggregate 第 1 份结果算 count 和 mean(score)。"
            ),
            snapshots=[SLICE, BROAD],
            batch=["slice10", "full"],
            input={"result_ref": SLICE["result_ref"]},
            metrics=[{"op": "count", "as": "n"}, {"op": "mean", "field": "score", "as": "avg"}],
            bind="auto",
            expect_result_ref=SLICE["result_ref"],
        ),
        Scenario(
            id="stale_ref_corrected_to_batch_full",
            category="rule_correction",
            snapshots=[BROAD],
            batch=["full"],
            input={"result_ref": "query-results/stale-limit.json"},
            metrics=[{"op": "count", "as": "n"}],
            expect_result_ref=BROAD["result_ref"],
        ),
        Scenario(
            id="cross_turn_ref_rejected",
            category="guard_negative",
            user_turn=2,
            prior_datasets=[
                {
                    "dataset_id": "ds_old",
                    "result_ref": "query-results/old-turn.json",
                    "user_turn": 1,
                    "result_rows": 10,
                    "query_limit": 10,
                }
            ],
            input={"result_ref": "query-results/old-turn.json"},
            metrics=[{"op": "count", "as": "n"}],
            expect_error=True,
            expect_error_contains="上一轮",
        ),
        Scenario(
            id="cross_turn_allowed_via_dataset_id",
            category="cross_turn_explicit",
            user_turn=2,
            prior_datasets=[
                {
                    "dataset_id": "ds_keep",
                    "result_ref": "query-results/prior.json",
                    "user_turn": 1,
                    "result_rows": 10,
                    "query_limit": 10,
                }
            ],
            input={"dataset_id": "ds_keep"},
            metrics=[{"op": "mean", "field": "score", "as": "avg"}],
            bind="chain",
            expect_result_ref="query-results/prior.json",
            expect_dataset_id="ds_keep",
        ),
        Scenario(
            id="no_turn_data_error",
            category="guard_negative",
            metrics=[{"op": "count", "as": "n"}],
            expect_error=True,
            expect_error_contains="缺少可用",
        ),
        Scenario(
            id="unknown_dataset_id_error",
            category="guard_negative",
            input={"dataset_id": "ds_missing"},
            metrics=[{"op": "count", "as": "n"}],
            expect_error=True,
            expect_error_contains="未知 dataset_id",
        ),
        Scenario(
            id="unknown_chain_id_error",
            category="guard_negative",
            input={"chain_from_dataset_id": "ds_nope"},
            metrics=[{"op": "count", "as": "n"}],
            expect_error=True,
            expect_error_contains="未知 chain_from_dataset_id",
        ),
        Scenario(
            id="three_candidates_fresh_class_wide",
            category="rule_scoring",
            teacher_message="全班整体 distinct student 规模",
            snapshots=[SLICE, MID, BROAD],
            metrics=[{"op": "count_distinct", "field": "student_ID", "as": "n"}],
            bind="fresh",
            expect_result_ref=BROAD["result_ref"],
        ),
    ]


def _snapshot_index() -> dict[str, dict[str, Any]]:
    return {
        "slice10": SLICE,
        "full": BROAD,
        "mid100": MID,
    }


def _session_id(scenario_id: str) -> str:
    return f"{EVAL_SESSION_PREFIX}{scenario_id}"


def _cleanup_session(session_id: str) -> None:
    path = AGENT_STATE_DIR / "sessions" / session_id
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


def _prepare_session(scenario: Scenario) -> str:
    sid = _session_id(scenario.id)
    _cleanup_session(sid)
    for row in scenario.prior_datasets:
        append_dataset(
            sid,
            DatasetRecord(
                dataset_id=str(row["dataset_id"]),
                result_ref=str(row["result_ref"]),
                user_turn=int(row.get("user_turn", 1)),
                result_rows=int(row.get("result_rows", 0)),
                query_limit=row.get("query_limit"),
                rows_scanned=row.get("rows_scanned"),
                resource=row.get("resource"),
            ),
        )
    return sid


def _resolve_snapshots(scenario: Scenario) -> tuple[list[QuerySnapshot], list[QuerySnapshot]]:
    idx = _snapshot_index()
    snaps = [_snap(s) for s in scenario.snapshots]
    if scenario.batch:
        batch = [_snap(idx[key]) for key in scenario.batch]
    else:
        batch = list(snaps)
    return snaps, batch


def run_scenario(scenario: Scenario) -> dict[str, Any]:
    session_id = _prepare_session(scenario)
    ctx = AnalysisToolContext(session_id=session_id, user_turn=scenario.user_turn)
    ctx.current_user_message = scenario.teacher_message or None

    turn_snaps, batch_snaps = _resolve_snapshots(scenario)
    for snap in turn_snaps:
        ctx.register_query_snapshot(snap)

    binding = resolve_aggregate_binding(
        dict(scenario.input),
        metrics=list(scenario.metrics),
        dimensions=None,
        bind=BindMode.parse(scenario.bind),
        analysis_context=ctx,
        batch_snapshots=batch_snaps,
        llm_client=None,
    )

    ok = True
    reasons: list[str] = []

    if scenario.expect_error:
        if not binding.error:
            ok = False
            reasons.append("expected Error but binding succeeded")
        elif scenario.expect_error_contains and scenario.expect_error_contains not in binding.error:
            ok = False
            reasons.append(f"error missing substring: {scenario.expect_error_contains!r}")
    else:
        if binding.error:
            ok = False
            reasons.append(f"unexpected error: {binding.error[:120]}")
        if scenario.expect_result_ref and binding.result_ref != scenario.expect_result_ref:
            ok = False
            reasons.append(
                f"result_ref {binding.result_ref!r} != expected {scenario.expect_result_ref!r}"
            )
        if scenario.expect_dataset_id and binding.dataset_id != scenario.expect_dataset_id:
            ok = False
            reasons.append(
                f"dataset_id {binding.dataset_id!r} != expected {scenario.expect_dataset_id!r}"
            )

    return {
        "id": scenario.id,
        "category": scenario.category,
        "ok": ok,
        "reasons": reasons,
        "result_ref": binding.result_ref,
        "dataset_id": binding.dataset_id,
        "error": (binding.error or "")[:200] if binding.error else None,
        "decision": binding.decision,
        "resolver": (binding.trace or {}).get("resolver") if binding.trace else None,
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    correct = sum(1 for r in results if r["ok"])
    by_cat: dict[str, dict[str, int]] = {}
    for r in results:
        cat = r["category"]
        by_cat.setdefault(cat, {"total": 0, "correct": 0})
        by_cat[cat]["total"] += 1
        if r["ok"]:
            by_cat[cat]["correct"] += 1

    cat_rates = {
        cat: round(100 * v["correct"] / v["total"], 2) if v["total"] else 0.0
        for cat, v in sorted(by_cat.items())
    }

    failures = [r for r in results if not r["ok"]]

    return {
        "total": total,
        "correct": correct,
        "accuracy_pct": round(100 * correct / total, 2) if total else 0.0,
        "by_category": cat_rates,
        "failures": failures,
        "resolver_mode": "rules+heuristic (BINDING_RESOLVER_DISABLE_LLM=1)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def render_report(summary: dict[str, Any], results: list[dict[str, Any]]) -> str:
    cat_lines = [
        "| 类别 | 正确/总数 | 准确率 |",
        "|------|-----------|--------|",
    ]
    counts: dict[str, dict[str, int]] = {}
    for r in results:
        counts.setdefault(r["category"], {"t": 0, "c": 0})
        counts[r["category"]]["t"] += 1
        if r["ok"]:
            counts[r["category"]]["c"] += 1
    for cat in sorted(counts):
        t, c = counts[cat]["t"], counts[cat]["c"]
        rate = summary["by_category"].get(cat, 0)
        cat_lines.append(f"| `{cat}` | {c}/{t} | {rate}% |")

    fail_lines = ["| 场景 | 原因 |", "|------|------|"]
    for f in summary.get("failures") or []:
        fail_lines.append(f"| `{f['id']}` | {'; '.join(f['reasons'])} |")
    if len(fail_lines) == 2:
        fail_lines.append("| — | 无 |")

    acc = summary["accuracy_pct"]
    return f"""# Dataset Binding 准确率评测

> 生成时间：{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}  
> 脚本：`backend/agent/eval/binding_accuracy.py`

## 指标定义

**绑定准确率** = `resolve_aggregate_binding` 输出与期望一致的场景占比。

- **正例**：`result_ref` / `dataset_id` 与标注一致且无 Error
- **负例（guard）**：应拒绝绑定（如跨 turn 静默续用）且返回含预期提示的 Error

**评测模式**：`BINDING_RESOLVER_DISABLE_LLM=1`（规则打分 + 启发式意图，无 live LLM）

## 结果摘要

| 指标 | 值 |
|------|-----|
| 场景数 N | {summary["total"]} |
| 正确数 | {summary["correct"]} |
| **绑定准确率** | **{acc}%** |

## 按类别

{chr(10).join(cat_lines)}

## 失败场景

{chr(10).join(fail_lines)}

## 简历可用（一句话）

> 基于 N={summary["total"]} 个离线 binding 场景，aggregate 数据集绑定准确率 **{acc}%**（规则 + 启发式 resolver，含跨 turn 硬规则拦截）。

## 局限性

- 离线评测，不经过真实 `query_data` 扫库
- 歧义场景使用启发式 resolver（`BINDING_RESOLVER_DISABLE_LLM=1`）；生产环境 LLM intent 路径未计入
- 多切片并存且教师话含「这些」时，启发式取最后一个 slice 候选（见代码 `heuristic_resolve`）

## 复现

```bash
cd H:/WORKDIR/NorthClassVision
python backend/agent/eval/binding_accuracy.py
```
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Dataset binding accuracy eval")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    scenarios = build_scenarios()
    results: list[dict[str, Any]] = []
    try:
        for sc in scenarios:
            results.append(run_scenario(sc))
    finally:
        for sc in scenarios:
            _cleanup_session(_session_id(sc.id))

    summary = summarize(results)
    summary["results"] = results

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report_out.write_text(render_report(summary, results), encoding="utf-8")

    print(f"Binding accuracy: {summary['accuracy_pct']}% ({summary['correct']}/{summary['total']})")
    for cat, rate in summary["by_category"].items():
        print(f"  {cat}: {rate}%")
    if summary["failures"]:
        print("Failures:")
        for f in summary["failures"]:
            print(f"  - {f['id']}: {f['reasons']}")
    print(f"Wrote {args.json_out}")
    print(f"Wrote {args.report_out}")
    return 0 if summary["correct"] == summary["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
