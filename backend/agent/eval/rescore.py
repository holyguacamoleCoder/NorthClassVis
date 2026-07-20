"""Offline re-score of a finished agent_benchmark.json (no LLM re-run).

Repairs turn_index skew caused by drop_previous deleting merged user turns,
then re-runs metrics against current scenario fixtures / binding_judge.
"""

from __future__ import annotations

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

from data.dataset_registry import DatasetRecord  # noqa: E402
from eval.metrics import evaluate_all  # noqa: E402
from eval.repair_ui import _is_turn_final_assistant, _split_response_segments  # noqa: E402
from eval.report import render_markdown, summarize  # noqa: E402
from eval.schema import load_scenarios  # noqa: E402
from eval.trace import RunTrace, ToolCallEvent, UsageStats, extract_tool_events  # noqa: E402


def _align_segments(segments: list[list[dict[str, Any]]], n_turns: int) -> list[list[dict[str, Any]]]:
    if n_turns <= 0:
        return []
    if len(segments) > n_turns:
        head = segments[: n_turns - 1]
        tail: list[dict[str, Any]] = []
        for seg in segments[n_turns - 1 :]:
            tail.extend(seg)
        return head + ([tail] if tail else [[]])
    while len(segments) < n_turns:
        segments.append([])
    return segments


def rebuild_messages_with_turn_markers(
    messages: list[dict[str, Any]],
    n_turns: int,
) -> list[dict[str, Any]]:
    """Insert synthetic user messages so extract_tool_events gets 0..n-1 turns."""
    segments = _align_segments(_split_response_segments(list(messages or [])), n_turns)
    rebuilt: list[dict[str, Any]] = []
    for i, seg in enumerate(segments):
        rebuilt.append({"role": "user", "content": f"__rescored_turn_{i}__"})
        rebuilt.extend(seg)
    return rebuilt


def _catalog_from_dicts(rows: list[dict[str, Any]] | None) -> list[DatasetRecord]:
    out: list[DatasetRecord] = []
    for c in rows or []:
        if not isinstance(c, dict):
            continue
        out.append(
            DatasetRecord(
                dataset_id=str(c.get("dataset_id") or ""),
                result_ref=str(c.get("result_ref") or ""),
                user_turn=int(c.get("user_turn") or 0),
                result_rows=c.get("result_rows"),
                query_limit=c.get("query_limit"),
                rows_scanned=c.get("rows_scanned"),
            )
        )
    return out


def _usage_from_dict(raw: dict[str, Any] | None) -> UsageStats:
    raw = raw or {}
    return UsageStats(
        input_tokens=int(raw.get("input_tokens") or 0),
        output_tokens=int(raw.get("output_tokens") or 0),
        cached_tokens=int(raw.get("cached_tokens") or 0),
        llm_calls=int(raw.get("llm_calls") or 0),
    )


def trace_from_run_dict(row: dict[str, Any], *, n_turns: int) -> RunTrace:
    messages = list(row.get("messages") or [])
    rebuilt = rebuild_messages_with_turn_markers(messages, n_turns)
    events = extract_tool_events(rebuilt)

    # Prefer content/meta already captured on stored tool_calls when re-extract is thin.
    by_id = {
        str(e.get("tool_call_id") or ""): e
        for e in (row.get("tool_calls") or [])
        if isinstance(e, dict) and e.get("tool_call_id")
    }
    merged: list[ToolCallEvent] = []
    for ev in events:
        prev = by_id.get(ev.tool_call_id)
        if prev:
            content = str(prev.get("content") or ev.content or "")
            meta = dict(prev.get("meta") or ev.meta or {})
            tool_input = prev.get("tool_input")
            if not isinstance(tool_input, dict):
                tool_input = ev.tool_input
            merged.append(
                ToolCallEvent(
                    turn_index=ev.turn_index,
                    ordinal=ev.ordinal,
                    name=ev.name,
                    tool_call_id=ev.tool_call_id,
                    tool_input=dict(tool_input or {}),
                    content=content,
                    meta=meta,
                    is_error=bool(prev.get("is_error", ev.is_error)),
                    resolver=prev.get("resolver") or ev.resolver,
                )
            )
        else:
            merged.append(ev)

    user_contents = [
        str(m.get("content") or "")
        for m in rebuilt
        if m.get("role") == "user" and isinstance(m.get("content"), str)
    ]
    if not user_contents:
        user_contents = [f"__rescored_turn_{i}__" for i in range(n_turns)]

    return RunTrace(
        scenario_id=str(row.get("scenario_id") or ""),
        run_index=int(row.get("run_index") or 0),
        session_id=str(row.get("session_id") or ""),
        status=str(row.get("status") or "ok"),
        error=row.get("error"),
        duration_sec=float(row.get("duration_sec") or 0),
        turn_durations_sec=list(row.get("turn_durations_sec") or []),
        continue_reason=row.get("continue_reason"),
        tool_calls=merged,
        user_contents=user_contents,
        messages=rebuilt,
        catalog=_catalog_from_dicts(row.get("catalog")),
        usage=_usage_from_dict(row.get("usage")),
        failure_tags=[],
        metric_results=[],
        dry_run=bool(row.get("dry_run")),
        benchmark_run_id=row.get("benchmark_run_id"),
        provider_model=row.get("provider_model"),
        provider_base_url=row.get("provider_base_url"),
        session_kept=bool(row.get("session_kept")),
    )


def rescore_benchmark_json(
    source: Path,
    *,
    scenarios_root: Path | None = None,
    json_out: Path | None = None,
    report_out: Path | None = None,
) -> dict[str, Any]:
    raw = json.loads(source.read_text(encoding="utf-8"))
    scen_root = scenarios_root or (AGENT_ROOT / "eval" / "fixtures" / "scenarios")
    scenarios = load_scenarios(scen_root, include_disabled=True, include_extended=True)
    by_id = {s.id: s for s in scenarios}

    traces: list[RunTrace] = []
    for row in raw.get("runs") or []:
        sc = by_id.get(row.get("scenario_id"))
        if sc is None:
            continue
        tr = trace_from_run_dict(row, n_turns=len(sc.turns))
        tr.metric_results = []
        evaluate_all(sc, tr)
        hard = [m for m in tr.metric_results if m.get("hard_gate", True)]
        if hard and all(m.get("passed") for m in hard):
            if tr.status in ("failed", "ok"):
                tr.status = "ok"
        elif hard and tr.status == "ok":
            tr.status = "failed"
        traces.append(tr)

    manifest = dict(raw.get("manifest") or {})
    manifest["rescored_at"] = datetime.now(timezone.utc).isoformat()
    manifest["rescore_note"] = (
        "offline turn repair + metrics re-eval; no LLM re-run; "
        "reject_cross_turn accepts explicit dataset_id"
    )
    summary = summarize(
        traces,
        scenarios=scenarios,
        runs_per_scenario=int(raw.get("N_runs_per_scenario") or 3),
        pass_strategy=str(raw.get("pass_strategy") or "majority"),
        manifest=manifest,
        finished_at=datetime.now(timezone.utc).isoformat(),
    )
    json_path = json_out or (source.parent / "agent_benchmark.rescored.json")
    report_path = report_out or (source.parent / "report-rescored.md")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_markdown(summary), encoding="utf-8")
    # Compat copies for docs / fixed legacy paths.
    from eval.archive import LEGACY_RESCORED_JSON, LEGACY_RESCORED_REPORT

    LEGACY_RESCORED_JSON.parent.mkdir(parents=True, exist_ok=True)
    LEGACY_RESCORED_REPORT.parent.mkdir(parents=True, exist_ok=True)
    LEGACY_RESCORED_JSON.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    LEGACY_RESCORED_REPORT.write_text(report_path.read_text(encoding="utf-8"), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    import argparse

    from eval.archive import resolve_source_json

    p = argparse.ArgumentParser(description="Offline re-score agent benchmark JSON")
    p.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Source agent_benchmark.json (default: latest.json pointer)",
    )
    p.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Default: <source-dir>/agent_benchmark.rescored.json",
    )
    p.add_argument(
        "--report-out",
        type=Path,
        default=None,
        help="Default: <source-dir>/report-rescored.md",
    )
    args = p.parse_args(argv)
    source = resolve_source_json(args.source)
    json_out = args.json_out or (source.parent / "agent_benchmark.rescored.json")
    report_out = args.report_out or (source.parent / "report-rescored.md")
    summary = rescore_benchmark_json(source, json_out=json_out, report_out=report_out)
    eff = summary.get("efficiency") or {}
    print(
        f"rescored: pass@1={summary.get('pass_at_1_pct')}% "
        f"pass@k={summary.get('pass_at_k_pct')}% "
        f"binding={summary.get('binding_accuracy_pct')}% "
        f"all_p50={eff.get('median_duration_sec_all')}s "
        f"all_p95={eff.get('p95_duration_sec_all')}s"
    )
    print(f"source: {source}")
    print(f"json: {json_out}")
    print(f"report: {report_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
