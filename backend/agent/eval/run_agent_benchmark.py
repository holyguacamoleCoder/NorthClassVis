#!/usr/bin/env python3
"""Agent benchmark CLI.

Usage (repo root):
    python backend/agent/eval/run_agent_benchmark.py --dry-run
    python backend/agent/eval/run_agent_benchmark.py --runs 3
    python backend/agent/eval/run_agent_benchmark.py --tags binding,tools --runs 1
    python backend/agent/eval/run_agent_benchmark.py --scenario chain_slice_two_turns --runs 1

Defaults (beneficial for avoiding re-runs):
    - outputs under data/eval/runs/{benchmark_run_id}/
    - latest.json pointer + index.jsonl (history never overwritten)
    - legacy fixed paths refreshed as copies of latest
    - incremental checkpoint after each session-run
    - keep failed session artifacts on disk (on-failure)
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

for _mod in ("http.client", "http.cookiejar"):
    if _mod not in sys.modules:
        importlib.import_module(_mod)

AGENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import runtime_bootstrap  # noqa: F401, E402

from eval.archive import default_output_paths, publish_latest  # noqa: E402
from eval.checkpoint import append_run_checkpoint, init_checkpoint, write_manifest_file  # noqa: E402
from eval.manifest import build_run_manifest, new_benchmark_run_id  # noqa: E402
from eval.report import render_markdown, summarize  # noqa: E402
from eval.runner import RUN_TIMEOUT_SEC, run_scenario, run_with_timeout  # noqa: E402
from eval.schema import load_scenarios, validate_scenarios  # noqa: E402
from eval.trace import RunTrace  # noqa: E402

DEFAULT_SCENARIOS = Path(__file__).resolve().parent / "fixtures" / "scenarios"


def main() -> int:
    parser = argparse.ArgumentParser(description="Universal agent benchmark harness")
    parser.add_argument(
        "--scenarios",
        type=Path,
        default=DEFAULT_SCENARIOS,
        help="Scenario JSON file or directory (default: fixtures/scenarios)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Run output directory (default: data/eval/runs/{benchmark_run_id})",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Override summary JSON path (default: <out-dir>/agent_benchmark.json)",
    )
    parser.add_argument(
        "--report-out",
        type=Path,
        default=None,
        help="Override markdown report path (default: <out-dir>/report.md)",
    )
    parser.add_argument(
        "--checkpoint-out",
        type=Path,
        default=None,
        help="Incremental JSONL checkpoint (default: <out-dir>/agent_benchmark.partial.jsonl)",
    )
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=None,
        help="Run manifest JSON (default: <out-dir>/manifest.json)",
    )
    parser.add_argument(
        "--no-checkpoint",
        action="store_true",
        help="Disable incremental checkpoint (not recommended)",
    )
    parser.add_argument(
        "--no-latest",
        action="store_true",
        help="Skip writing latest.json / legacy compat copies",
    )
    parser.add_argument(
        "--keep-session",
        choices=("never", "on-failure", "always"),
        default="on-failure",
        help="Retain .agent session dirs: on-failure (default), always, or never",
    )
    parser.add_argument("--runs", type=int, default=3, help="Runs per scenario (smoke=1, regression=3, release=8)")
    parser.add_argument("--scenario", type=str, default=None, help="Single scenario id")
    parser.add_argument(
        "--tags",
        type=str,
        default=None,
        help="Comma-separated tags filter (e.g. binding,tools). "
        "Include scope-extended to run extended scope scenarios.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Synthetic traces, no LLM")
    parser.add_argument("--timeout", type=int, default=RUN_TIMEOUT_SEC)
    parser.add_argument(
        "--pass-strategy",
        choices=("any_pass", "majority", "all_pass"),
        default="majority",
    )
    args = parser.parse_args()

    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None
    scenarios = load_scenarios(args.scenarios, tags=tags, scenario_id=args.scenario)
    if not scenarios:
        print("No scenarios matched.")
        return 2

    errors = validate_scenarios(scenarios)
    if errors:
        print("Scenario validation errors:")
        for e in errors:
            print(f"  - {e}")
        return 2

    benchmark_run_id = new_benchmark_run_id()
    started_at = datetime.now(timezone.utc)
    paths = default_output_paths(benchmark_run_id)
    run_dir = args.out_dir or paths["run_dir"]
    run_dir.mkdir(parents=True, exist_ok=True)
    json_out = args.json_out or (run_dir / "agent_benchmark.json")
    report_out = args.report_out or (run_dir / "report.md")
    checkpoint_out = args.checkpoint_out or (run_dir / "agent_benchmark.partial.jsonl")
    manifest_out = args.manifest_out or (run_dir / "manifest.json")

    llm_client = None
    if not args.dry_run:
        from common.llm_client import LLMClient

        llm_client = LLMClient()

    manifest = build_run_manifest(
        benchmark_run_id=benchmark_run_id,
        scenarios_root=args.scenarios,
        scenario_ids=[s.id for s in scenarios],
        runs_per_scenario=args.runs,
        dry_run=args.dry_run,
        pass_strategy=args.pass_strategy,
        timeout_sec=args.timeout,
        keep_session=args.keep_session,
        checkpoint_path=checkpoint_out,
        json_out=json_out,
        report_out=report_out,
        tags=tags,
        scenario_filter=args.scenario,
        llm_client=llm_client,
        started_at=started_at,
    )
    write_manifest_file(manifest_out, manifest)
    if not args.no_checkpoint:
        init_checkpoint(checkpoint_out, manifest)
    print(f"benchmark_run_id={benchmark_run_id}")
    print(f"out_dir={run_dir}")
    print(f"Wrote manifest {manifest_out}")

    traces: list[RunTrace] = []
    for scenario in scenarios:
        for run_idx in range(args.runs):
            print(f"Running {scenario.id} run {run_idx + 1}/{args.runs} ...")

            def _task(sc=scenario, ri=run_idx):
                return run_scenario(
                    sc,
                    run_index=ri,
                    llm_client=llm_client,
                    dry_run=args.dry_run,
                    timeout_sec=args.timeout,
                    keep_session_policy=args.keep_session,
                    benchmark_run_id=benchmark_run_id,
                )

            if args.dry_run:
                tr = _task()
            else:
                tr = run_with_timeout(_task, args.timeout)
                if tr.scenario_id == "unknown":
                    tr.scenario_id = scenario.id
                    tr.run_index = run_idx
                    tr.session_id = f"agent-bench-{scenario.id}-r{run_idx}"
                    tr.benchmark_run_id = benchmark_run_id
            traces.append(tr)

            if not args.no_checkpoint:
                append_run_checkpoint(
                    checkpoint_out,
                    tr,
                    benchmark_run_id=benchmark_run_id,
                )

            hard = [m for m in tr.metric_results if m.get("hard_gate", True)]
            ok_n = sum(1 for m in hard if m.get("passed"))
            tot_n = len(hard) or 0
            kept = " kept" if tr.session_kept else ""
            print(
                f"  status={tr.status} hard={ok_n}/{tot_n} "
                f"tools={len(tr.tool_calls)} duration={tr.duration_sec}s{kept}"
            )

    finished_at = datetime.now(timezone.utc).isoformat()
    manifest["finished_at"] = finished_at
    manifest["N_session_runs_completed"] = len(traces)
    write_manifest_file(manifest_out, manifest)

    summary = summarize(
        traces,
        scenarios=scenarios,
        runs_per_scenario=args.runs,
        pass_strategy=args.pass_strategy,
        manifest=manifest,
        finished_at=finished_at,
    )

    json_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_out.write_text(render_markdown(summary), encoding="utf-8")

    if not args.no_latest:
        meta = publish_latest(
            benchmark_run_id=benchmark_run_id,
            run_dir=run_dir,
            summary=summary,
            json_out=json_out,
            report_out=report_out,
            checkpoint_out=checkpoint_out,
            manifest_out=manifest_out,
        )
        print(f"Wrote latest pointer {meta.get('dir')}")

    print(
        f"pass@1={summary['pass_at_1_pct']}%  pass@k={summary['pass_at_k_pct']}%  "
        f"binding={summary.get('binding_accuracy_pct')}%"
    )
    print(f"Wrote {json_out}")
    print(f"Wrote {report_out}")
    if not args.no_checkpoint:
        print(f"Wrote checkpoint {checkpoint_out}")

    all_ok = all(s.get("scenario_pass") for s in summary.get("scenarios") or [])
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
