"""Incremental checkpoint writer for benchmark runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eval.trace import RunTrace


def init_checkpoint(path: Path, manifest: dict[str, Any]) -> None:
    """Start a fresh checkpoint file for this benchmark run."""
    path.parent.mkdir(parents=True, exist_ok=True)
    header = {
        "type": "manifest",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "manifest": manifest,
    }
    path.write_text(json.dumps(header, ensure_ascii=False) + "\n", encoding="utf-8")


def append_run_checkpoint(
    path: Path,
    trace: RunTrace,
    *,
    benchmark_run_id: str,
) -> None:
    row = {
        "type": "run",
        "benchmark_run_id": benchmark_run_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "scenario_id": trace.scenario_id,
        "run_index": trace.run_index,
        "session_id": trace.session_id,
        "status": trace.status,
        "trace": trace.to_dict(),
    }
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_manifest_file(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def load_checkpoint_runs(path: Path, *, benchmark_run_id: str | None = None) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    runs: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("type") != "run":
            continue
        if benchmark_run_id and row.get("benchmark_run_id") != benchmark_run_id:
            continue
        runs.append(row)
    return runs
