"""Per-run archival helpers for agent benchmark outputs."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
EVAL_ROOT = REPO_ROOT / "data" / "eval"
RUNS_ROOT = EVAL_ROOT / "runs"
LATEST_PATH = EVAL_ROOT / "latest.json"
INDEX_PATH = RUNS_ROOT / "index.jsonl"

LEGACY_JSON = EVAL_ROOT / "agent_benchmark.json"
LEGACY_CHECKPOINT = EVAL_ROOT / "agent_benchmark.partial.jsonl"
LEGACY_MANIFEST = EVAL_ROOT / "agent_benchmark.manifest.json"
LEGACY_REPORT = REPO_ROOT / "docs" / "eval" / "agent-benchmark-report.md"
LEGACY_RESCORED_JSON = EVAL_ROOT / "agent_benchmark.rescored.json"
LEGACY_RESCORED_REPORT = REPO_ROOT / "docs" / "eval" / "agent-benchmark-report-rescored.md"


def run_dir_for(benchmark_run_id: str) -> Path:
    return RUNS_ROOT / benchmark_run_id


def default_output_paths(benchmark_run_id: str) -> dict[str, Path]:
    run_dir = run_dir_for(benchmark_run_id)
    return {
        "run_dir": run_dir,
        "json_out": run_dir / "agent_benchmark.json",
        "checkpoint_out": run_dir / "agent_benchmark.partial.jsonl",
        "manifest_out": run_dir / "manifest.json",
        "report_out": run_dir / "report.md",
    }


def _copy_if_exists(src: Path, dest: Path) -> None:
    if not src.is_file():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def publish_latest(
    *,
    benchmark_run_id: str,
    run_dir: Path,
    summary: dict[str, Any] | None = None,
    json_out: Path | None = None,
    report_out: Path | None = None,
    checkpoint_out: Path | None = None,
    manifest_out: Path | None = None,
) -> dict[str, Any]:
    """Write latest.json, append index.jsonl, refresh legacy compat copies."""
    run_dir = Path(run_dir)
    meta = {
        "benchmark_run_id": benchmark_run_id,
        "dir": str(run_dir.resolve()),
        "finished_at": (summary or {}).get("finished_at")
        or datetime.now(timezone.utc).isoformat(),
        "pass_at_1_pct": (summary or {}).get("pass_at_1_pct"),
        "pass_at_k_pct": (summary or {}).get("pass_at_k_pct"),
        "binding_accuracy_pct": (summary or {}).get("binding_accuracy_pct"),
        "N_session_runs": (summary or {}).get("N_session_runs"),
        "json": str((json_out or run_dir / "agent_benchmark.json").resolve()),
        "report": str((report_out or run_dir / "report.md").resolve()),
    }
    EVAL_ROOT.mkdir(parents=True, exist_ok=True)
    RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    LATEST_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with INDEX_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(meta, ensure_ascii=False) + "\n")

    # Legacy fixed paths = copy of latest (compat for old docs / scripts).
    if json_out and json_out.is_file():
        _copy_if_exists(json_out, LEGACY_JSON)
    if report_out and report_out.is_file():
        _copy_if_exists(report_out, LEGACY_REPORT)
    if checkpoint_out and checkpoint_out.is_file():
        _copy_if_exists(checkpoint_out, LEGACY_CHECKPOINT)
    if manifest_out and manifest_out.is_file():
        _copy_if_exists(manifest_out, LEGACY_MANIFEST)
    return meta


def read_latest() -> dict[str, Any] | None:
    if not LATEST_PATH.is_file():
        return None
    raw = json.loads(LATEST_PATH.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else None


def resolve_source_json(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit
    latest = read_latest()
    if latest and latest.get("json"):
        p = Path(str(latest["json"]))
        if p.is_file():
            return p
    if LEGACY_JSON.is_file():
        return LEGACY_JSON
    raise FileNotFoundError("no benchmark JSON found (latest.json / legacy path)")


def migrate_legacy_run(
    *,
    benchmark_run_id: str,
    force: bool = False,
) -> Path:
    """Copy current fixed-path artifacts into runs/{id}/ once."""
    dest = run_dir_for(benchmark_run_id)
    if dest.exists() and not force:
        return dest
    dest.mkdir(parents=True, exist_ok=True)
    mapping = [
        (LEGACY_JSON, dest / "agent_benchmark.json"),
        (LEGACY_CHECKPOINT, dest / "agent_benchmark.partial.jsonl"),
        (LEGACY_MANIFEST, dest / "manifest.json"),
        (LEGACY_REPORT, dest / "report.md"),
        (LEGACY_RESCORED_JSON, dest / "agent_benchmark.rescored.json"),
        (LEGACY_RESCORED_REPORT, dest / "report-rescored.md"),
    ]
    for src, out in mapping:
        _copy_if_exists(src, out)
    # Prefer manifest id if present
    man = dest / "manifest.json"
    if man.is_file():
        try:
            mid = (json.loads(man.read_text(encoding="utf-8")) or {}).get("benchmark_run_id")
            if mid and mid != benchmark_run_id:
                # keep files under requested id; record note
                (dest / "MIGRATED_FROM.txt").write_text(
                    f"requested={benchmark_run_id}\nmanifest_id={mid}\n",
                    encoding="utf-8",
                )
        except Exception:
            pass
    summary = None
    js = dest / "agent_benchmark.json"
    if js.is_file():
        try:
            summary = json.loads(js.read_text(encoding="utf-8"))
        except Exception:
            summary = None
    publish_latest(
        benchmark_run_id=benchmark_run_id,
        run_dir=dest,
        summary=summary if isinstance(summary, dict) else None,
        json_out=js if js.is_file() else None,
        report_out=dest / "report.md",
        checkpoint_out=dest / "agent_benchmark.partial.jsonl",
        manifest_out=dest / "manifest.json",
    )
    return dest
