"""Merge multiple agent_benchmark JSON runs and recompute a unified report.

Later overlays win per (scenario_id, run_index). Zero-token / empty runs are
skipped when overlaying so balance-failed stubs do not clobber good traces.
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AGENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))

from eval.archive import publish_latest  # noqa: E402
from eval.manifest import new_benchmark_run_id  # noqa: E402
from eval.report import render_markdown  # noqa: E402
from eval.rescore import rescore_benchmark_json  # noqa: E402


def _usage_llm_calls(run: dict[str, Any]) -> int:
    u = run.get("usage") or {}
    return int(u.get("llm_calls") or 0)


def _is_void_run(run: dict[str, Any]) -> bool:
    """Balance / boot failures: no LLM work."""
    if _usage_llm_calls(run) > 0:
        return False
    if run.get("tool_calls"):
        return False
    if float(run.get("duration_sec") or 0) > 10:
        return False
    return True


def _run_key(run: dict[str, Any]) -> tuple[str, int]:
    return (str(run.get("scenario_id") or ""), int(run.get("run_index") or 0))


def merge_run_lists(
    base_runs: list[dict[str, Any]],
    overlays: list[list[dict[str, Any]]],
    *,
    skip_void_overlays: bool = True,
) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, int], dict[str, Any]] = {}
    for run in base_runs:
        by_key[_run_key(run)] = deepcopy(run)
    for layer in overlays:
        for run in layer:
            if skip_void_overlays and _is_void_run(run):
                continue
            by_key[_run_key(run)] = deepcopy(run)
    return [by_key[k] for k in sorted(by_key.keys(), key=lambda x: (x[0], x[1]))]


def load_runs(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw, list(raw.get("runs") or [])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Merge benchmark JSON runs into one report")
    p.add_argument("--base", type=Path, required=True, help="Full baseline agent_benchmark.json")
    p.add_argument(
        "--overlay",
        type=Path,
        action="append",
        default=[],
        help="Overlay JSON (repeatable); later flags win",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output run directory (default: data/eval/runs/{new_id})",
    )
    args = p.parse_args(argv)

    base_raw, base_runs = load_runs(args.base)
    overlay_runs: list[list[dict[str, Any]]] = []
    overlay_ids: list[str] = []
    for op in args.overlay:
        raw, runs = load_runs(op)
        overlay_runs.append(runs)
        overlay_ids.append(
            str((raw.get("manifest") or {}).get("benchmark_run_id") or op.parent.name)
        )

    merged_runs = merge_run_lists(base_runs, overlay_runs, skip_void_overlays=True)
    run_id = new_benchmark_run_id()
    out_dir = args.out_dir or (REPO_ROOT / "data" / "eval" / "runs" / run_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_out = out_dir / "agent_benchmark.json"
    report_out = out_dir / "report.md"
    manifest_out = out_dir / "manifest.json"
    staging = out_dir / "agent_benchmark.merged_raw.json"

    merge_meta = {
        "base": str(args.base.resolve()),
        "base_run_id": (base_raw.get("manifest") or {}).get("benchmark_run_id"),
        "overlays": [str(p.resolve()) for p in args.overlay],
        "overlay_run_ids": overlay_ids,
        "note": "later overlays win; void (0-token) overlay rows skipped; then offline rescore",
    }
    merged_doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "merge": merge_meta,
        "manifest": {
            **dict(base_raw.get("manifest") or {}),
            "benchmark_run_id": run_id,
            "merged_from": {
                "base": (base_raw.get("manifest") or {}).get("benchmark_run_id"),
                "overlays": overlay_ids,
            },
            "merge_kind": "overlay_by_scenario_run_index",
        },
        "N_runs_per_scenario": int(base_raw.get("N_runs_per_scenario") or 3),
        "pass_strategy": str(base_raw.get("pass_strategy") or "majority"),
        "runs": merged_runs,
    }
    staging.write_text(json.dumps(merged_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_out.write_text(
        json.dumps(merged_doc["manifest"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # Re-judge with current fixtures so headline matches suite hygiene.
    summary = rescore_benchmark_json(
        staging,
        json_out=json_out,
        report_out=report_out,
    )
    summary["merge"] = merge_meta
    json_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_out.write_text(render_markdown(summary), encoding="utf-8")

    publish_latest(
        benchmark_run_id=run_id,
        run_dir=out_dir,
        summary=summary,
        json_out=json_out,
        report_out=report_out,
        manifest_out=manifest_out,
    )
    print(f"merged_run_id={run_id}")
    print(f"out_dir={out_dir}")
    print(
        f"pass@1={summary.get('pass_at_1_pct')}% pass@k={summary.get('pass_at_k_pct')}% "
        f"binding={summary.get('binding_accuracy_pct')}% N={summary.get('N_session_runs')}"
    )
    print(f"report={report_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
