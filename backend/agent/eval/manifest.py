"""Run manifest: reproducibility metadata for benchmark sessions."""

from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

HARNESS_VERSION = "agent_benchmark_v1"


def _git_field(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if out.returncode != 0:
            return None
        return (out.stdout or "").strip() or None
    except Exception:
        return None


def scenario_fingerprint(scenario_paths: list[Path]) -> str:
    """Stable hash over scenario fixture contents."""
    h = hashlib.sha256()
    for path in sorted(scenario_paths):
        h.update(path.name.encode("utf-8"))
        h.update(path.read_bytes())
    return h.hexdigest()[:16]


def collect_scenario_paths(scenarios_root: Path) -> list[Path]:
    if scenarios_root.is_file():
        return [scenarios_root]
    return sorted(scenarios_root.glob("*.json"))


def build_run_manifest(
    *,
    benchmark_run_id: str,
    scenarios_root: Path,
    scenario_ids: list[str],
    runs_per_scenario: int,
    dry_run: bool,
    pass_strategy: str,
    timeout_sec: int,
    keep_session: str,
    checkpoint_path: Path,
    json_out: Path,
    report_out: Path,
    tags: list[str] | None = None,
    scenario_filter: str | None = None,
    llm_client: Any | None = None,
    started_at: datetime | None = None,
) -> dict[str, Any]:
    started = started_at or datetime.now(timezone.utc)
    paths = collect_scenario_paths(scenarios_root)
    cfg = getattr(llm_client, "config", None) if llm_client is not None else None
    model = getattr(cfg, "model", None) if cfg else os.environ.get("OPENAI_MODEL")
    base_url = getattr(cfg, "base_url", None) if cfg else os.environ.get("OPENAI_BASE_URL")

    langfuse_on = os.environ.get("LANGFUSE_ENABLED", "true").strip().lower() not in (
        "0",
        "false",
        "no",
    )
    return {
        "harness_version": HARNESS_VERSION,
        "benchmark_run_id": benchmark_run_id,
        "started_at": started.isoformat(),
        "dry_run": dry_run,
        "runs_per_scenario": runs_per_scenario,
        "pass_strategy": pass_strategy,
        "timeout_sec": timeout_sec,
        "keep_session": keep_session,
        "N_scenarios": len(scenario_ids),
        "scenario_ids": scenario_ids,
        "scenario_filter": scenario_filter,
        "tags_filter": tags or [],
        "scenarios_root": str(scenarios_root.resolve()),
        "scenario_fingerprint": scenario_fingerprint(paths) if paths else None,
        "scenario_files": [p.name for p in paths],
        "outputs": {
            "json": str(json_out.resolve()),
            "report_md": str(report_out.resolve()),
            "checkpoint_jsonl": str(checkpoint_path.resolve()),
            "manifest_json": str(checkpoint_path.with_name("agent_benchmark.manifest.json").resolve()),
        },
        "git": {
            "commit": _git_field("rev-parse", "HEAD"),
            "branch": _git_field("branch", "--show-current"),
            "dirty": bool(_git_field("status", "--porcelain")),
        },
        "provider": {
            "model": model,
            "base_url": base_url,
            "deepseek_thinking": os.environ.get("DEEPSEEK_THINKING_ENABLED", "true"),
        },
        "langfuse": {
            "enabled": langfuse_on,
            "redact_content": os.environ.get("LANGFUSE_REDACT_CONTENT", "1"),
            "base_url": os.environ.get("LANGFUSE_BASE_URL")
            or os.environ.get("LANGFUSE_HOST")
            or "https://cloud.langfuse.com",
            "filter_hint": {
                "session_id_prefix": "agent-bench-",
                "metadata": {
                    "eval_kind": "agent_benchmark",
                    "benchmark_run_id": benchmark_run_id,
                },
            },
        },
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
    }


def new_benchmark_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{ts}-{uuid4().hex[:8]}"
