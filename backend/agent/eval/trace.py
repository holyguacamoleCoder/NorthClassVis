"""Unified run trace extracted from AgentLoop message history."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from data.dataset_registry import DatasetRecord
from eval.binding_judge import recover_meta_from_partial_json, resolver_from_meta


@dataclass
class ToolCallEvent:
    turn_index: int
    ordinal: int  # 1-based within (turn, tool_name) or global per turn
    name: str
    tool_call_id: str
    tool_input: dict[str, Any]
    content: str
    meta: dict[str, Any] = field(default_factory=dict)
    is_error: bool = False
    resolver: str | None = None


@dataclass
class UsageStats:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    llm_calls: int = 0

    def add(self, other: "UsageStats") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cached_tokens += other.cached_tokens
        self.llm_calls += other.llm_calls

    @property
    def cache_hit_rate(self) -> float | None:
        if self.input_tokens <= 0:
            return None
        return round(self.cached_tokens / self.input_tokens, 4)


@dataclass
class RunTrace:
    scenario_id: str
    run_index: int
    session_id: str
    status: str = "ok"
    error: str | None = None
    duration_sec: float = 0.0
    turn_durations_sec: list[float] = field(default_factory=list)
    continue_reason: str | None = None
    tool_calls: list[ToolCallEvent] = field(default_factory=list)
    user_contents: list[str] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    catalog: list[DatasetRecord] = field(default_factory=list)
    usage: UsageStats = field(default_factory=UsageStats)
    failure_tags: list[str] = field(default_factory=list)
    metric_results: list[dict[str, Any]] = field(default_factory=list)
    dry_run: bool = False
    benchmark_run_id: str | None = None
    provider_model: str | None = None
    provider_base_url: str | None = None
    session_kept: bool = False

    def tool_calls_for(
        self,
        name: str | None = None,
        *,
        turn_index: int | None = None,
    ) -> list[ToolCallEvent]:
        out = self.tool_calls
        if name is not None:
            out = [e for e in out if e.name == name]
        if turn_index is not None:
            out = [e for e in out if e.turn_index == turn_index]
        return out

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["catalog"] = [
            {
                "dataset_id": c.dataset_id,
                "result_ref": c.result_ref,
                "user_turn": c.user_turn,
                "result_rows": c.result_rows,
                "query_limit": c.query_limit,
                "rows_scanned": c.rows_scanned,
            }
            for c in self.catalog
        ]
        return data


def _resolve_tool_result_content(content: str, call_id: str, tool_results_dir: Path | None) -> str:
    if call_id and tool_results_dir is not None:
        stored = tool_results_dir / f"{call_id}.txt"
        if stored.is_file():
            return stored.read_text(encoding="utf-8")
    return content


def _parse_args(args_raw: Any) -> dict[str, Any]:
    if isinstance(args_raw, dict):
        return dict(args_raw)
    if isinstance(args_raw, str):
        try:
            return json.loads(args_raw) if args_raw.strip() else {}
        except json.JSONDecodeError:
            return {"_raw_arguments": args_raw}
    return {}


def _is_error_content(content: str) -> bool:
    text = (content or "").strip()
    if not text:
        return False
    if text.startswith("Error:"):
        return True
    lower = text.lower()
    return "permission denied" in lower or "模式限制" in text or "不可用" in text


def extract_tool_events(
    messages: list[dict[str, Any]],
    *,
    tool_results_dir: Path | None = None,
) -> list[ToolCallEvent]:
    tool_results: dict[str, str] = {}
    for msg in messages:
        if msg.get("role") == "tool" and msg.get("tool_call_id"):
            tool_results[str(msg["tool_call_id"])] = str(msg.get("content") or "")

    events: list[ToolCallEvent] = []
    user_turn_idx = -1
    ordinals: dict[tuple[int, str], int] = {}

    for msg in messages:
        if msg.get("role") == "user":
            user_turn_idx += 1
            continue
        if msg.get("role") != "assistant":
            continue
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            name = str(fn.get("name") or tc.get("name") or "")
            if not name:
                continue
            call_id = str(tc.get("id") or "")
            key = (user_turn_idx, name)
            ordinals[key] = ordinals.get(key, 0) + 1
            ordinal = ordinals[key]
            tool_input = _parse_args(fn.get("arguments") or tc.get("arguments") or "{}")
            content = _resolve_tool_result_content(
                tool_results.get(call_id, ""), call_id, tool_results_dir
            )
            meta: dict[str, Any] = {}
            is_error = _is_error_content(content)
            if not is_error and content.strip():
                try:
                    payload = json.loads(content)
                    if isinstance(payload, dict):
                        meta = dict(payload.get("meta") or {})
                except json.JSONDecodeError:
                    meta = recover_meta_from_partial_json(content)
                    is_error = not meta
            events.append(
                ToolCallEvent(
                    turn_index=user_turn_idx,
                    ordinal=ordinal,
                    name=name,
                    tool_call_id=call_id,
                    tool_input=tool_input,
                    content=content,
                    meta=meta,
                    is_error=is_error,
                    resolver=resolver_from_meta(meta) if name == "aggregate_data" else None,
                )
            )
    return events


def extract_user_contents(messages: list[dict[str, Any]]) -> list[str]:
    return [str(m.get("content") or "") for m in messages if m.get("role") == "user"]


def usage_from_sdk(usage: Any) -> UsageStats:
    stats = UsageStats(llm_calls=1 if usage is not None else 0)
    if usage is None:
        return stats
    prompt = getattr(usage, "prompt_tokens", None) or getattr(usage, "input_tokens", None)
    completion = getattr(usage, "completion_tokens", None) or getattr(usage, "output_tokens", None)
    if prompt is None and isinstance(usage, dict):
        prompt = usage.get("prompt_tokens") or usage.get("input_tokens") or usage.get("input")
        completion = usage.get("completion_tokens") or usage.get("output_tokens") or usage.get("output")
    if prompt is not None:
        stats.input_tokens = int(prompt)
    if completion is not None:
        stats.output_tokens = int(completion)

    cached = getattr(usage, "prompt_cache_hit_tokens", None)
    if cached is None:
        cached = getattr(usage, "cache_read_input_tokens", None)
    if cached is None:
        for attr in ("prompt_tokens_details", "input_tokens_details"):
            nested = getattr(usage, attr, None)
            if nested is None and isinstance(usage, dict):
                nested = usage.get(attr)
            if nested is None:
                continue
            cached = getattr(nested, "cached_tokens", None)
            if cached is None and isinstance(nested, dict):
                cached = nested.get("cached_tokens") or nested.get("cache_read_tokens")
            if cached is not None:
                break
    if cached is None and isinstance(usage, dict):
        cached = (
            usage.get("prompt_cache_hit_tokens")
            or usage.get("cache_read_input_tokens")
            or usage.get("input_cached_tokens")
        )
    if cached is not None:
        stats.cached_tokens = int(cached)
    return stats
