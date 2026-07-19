"""Detect and classify query ↔ aggregate oscillation; suggest a new method."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from tools.runtime.pipeline.preprocess import parse_args

_AGGREGATE_TOOLS = frozenset({"aggregate_data"})
_QUERY_TOOL = "query_data"
_PRODUCTIVE_PROGRESS_TOOLS = frozenset({"aggregate_data", "enrich_data"})
_EXPLORATION_TOOLS = frozenset(
    {
        "inspect_schema",
        "read_file",
        "list_datasets",
        "list_files",
        "resolve_dataset_binding",
        "todo_write",
        "load_skill",
        "load_reference",
        "get_current_filter_context",
    }
)

_AGGREGATE_RETRY_MARKERS = (
    "绑定 scope=class_wide",
    "绑定 scope=chain_slice",
    "aggregate_data 需要 input",
    "input is required",
    "dataset_id",
    "RESULT_REF_CORRECTED",
)

_DS_ID_RE = re.compile(r"ds_[a-f0-9]+", re.IGNORECASE)
_REF_RE = re.compile(r"query-results/[a-f0-9]+\.json", re.IGNORECASE)
_ROW_COUNT_RE = re.compile(r"\d+\s*行")

# Oscillation kinds
KIND_AGG_ERROR_RETRY = "aggregate_error_retry"
KIND_REPEATED_QUERY = "repeated_identical_query"
KIND_PREVIEW_THRASH = "preview_truncation_thrash"
KIND_EXPLORATION_THRASH = "exploration_thrash"

_DEFAULT_PEEK_LIMIT = 50


@dataclass(frozen=True)
class OscillationEvent:
    kind: str
    soft: bool
    """True = inject redirect and continue; False = hard fuse stop."""
    title: str
    progress_lines: list[str]
    next_method_lines: list[str]


def normalize_aggregate_error(content: str) -> str | None:
    """Stable fingerprint for repeated aggregate failures (strip volatile ids)."""
    text = (content or "").strip()
    if not text.startswith("Error:"):
        return None
    if not any(marker in text for marker in _AGGREGATE_RETRY_MARKERS):
        return None
    line = text.split("\n", 1)[0]
    line = _DS_ID_RE.sub("ds_*", line)
    line = _REF_RE.sub("query-results/*.json", line)
    line = _ROW_COUNT_RE.sub("N行", line)
    return line[:240]


def normalize_query_data_signature(call: dict[str, Any]) -> str | None:
    """Ignore select/order_by/limit — only resource + class scope + week_range."""
    if call.get("name") != _QUERY_TOOL:
        return None
    args = parse_args(call.get("arguments", {}))
    resource = args.get("resource")
    if not resource:
        return None
    classes = args.get("classes")
    if classes is None and args.get("class"):
        classes = [args.get("class")]
    payload = {
        "resource": str(resource),
        "classes": sorted(str(c) for c in classes) if classes else None,
        "week_range": args.get("week_range"),
        "majors": sorted(str(m) for m in args.get("majors") or []) or None,
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def aggregate_errors_in_batch(
    tool_calls: list[dict[str, Any]],
    tool_results: list[dict[str, Any]],
) -> list[str]:
    by_id = {c.get("id"): c.get("name") for c in tool_calls if c.get("id")}
    for result in tool_results:
        if by_id.get(result.get("tool_call_id")) not in _AGGREGATE_TOOLS:
            continue
        sig = normalize_aggregate_error(str(result.get("content") or ""))
        if sig:
            return [sig]
    return []


def query_signatures_in_batch(tool_calls: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for call in tool_calls:
        sig = normalize_query_data_signature(call)
        if sig:
            out.append(sig)
    return out


def should_break_aggregate_retry_loop(
    recent_signatures: list[str],
    *,
    window: int,
) -> bool:
    if len(recent_signatures) < window:
        return False
    tail = recent_signatures[-window:]
    return len(set(tail)) == 1


def should_break_repeated_query_loop(
    recent_query_signatures: list[str],
    *,
    window: int,
    repeat_threshold: int,
) -> bool:
    if len(recent_query_signatures) < repeat_threshold:
        return False
    tail = recent_query_signatures[-window:]
    if not tail:
        return False
    from collections import Counter

    counts = Counter(tail)
    _sig, n = counts.most_common(1)[0]
    return n >= repeat_threshold


def normalize_success_agg_signature(
    tool_calls: list[dict[str, Any]],
    tool_results: list[dict[str, Any]],
) -> str | None:
    """Fingerprint successful aggregate_data (dims + whether preview-truncated)."""
    by_id = {c.get("id"): c for c in tool_calls if c.get("id")}
    for result in tool_results:
        call = by_id.get(result.get("tool_call_id"))
        if not call or call.get("name") != "aggregate_data":
            continue
        content = str(result.get("content") or "")
        if content.startswith("Error:"):
            continue
        args = parse_args(call.get("arguments", {}))
        dims = args.get("dimensions") or []
        has_order = bool(args.get("order_by"))
        has_limit = args.get("limit") is not None
        truncated = "truncated=True" in content or '"truncated": true' in content.lower()
        preview_only = "PREVIEW_ONLY" in content or "preview_only" in content
        payload = {
            "dims": sorted(str(d) for d in dims) if isinstance(dims, list) else [],
            "truncated_preview": bool(truncated or preview_only),
            "ordered": has_order,
            "limited": has_limit,
        }
        return json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return None


def should_break_preview_requery_oscillation(
    recent_pairs: list[str],
    *,
    threshold: int = 3,
) -> bool:
    if len(recent_pairs) < threshold:
        return False
    tail = recent_pairs[-threshold:]
    return len(set(tail)) == 1


def batch_has_productive_progress(tool_calls: list[dict[str, Any]]) -> bool:
    """True only for tools that actually advance accuracy/ranking (not meta explore)."""
    names = {str(c.get("name") or "") for c in tool_calls if c.get("name")}
    return bool(names & _PRODUCTIVE_PROGRESS_TOOLS)


def _is_peek_query(call: dict[str, Any], *, peek_limit: int) -> bool:
    if call.get("name") != _QUERY_TOOL:
        return False
    args = parse_args(call.get("arguments", {}))
    limit = args.get("limit")
    if limit is None:
        return False
    try:
        return int(limit) <= peek_limit
    except (TypeError, ValueError):
        return False


def is_exploration_only_batch(
    tool_calls: list[dict[str, Any]],
    *,
    peek_limit: int = _DEFAULT_PEEK_LIMIT,
) -> bool:
    """
    Meta/schema browsing + small-limit peeks + todo — no aggregate/enrich.

    Soft redirects intentionally allow a short exploration phase; this flag
    detects when that phase itself becomes the new oscillation.
    """
    if not tool_calls:
        return False
    if batch_has_productive_progress(tool_calls):
        return False
    for call in tool_calls:
        name = str(call.get("name") or "")
        if not name:
            continue
        if name in _EXPLORATION_TOOLS:
            continue
        if name == _QUERY_TOOL and _is_peek_query(call, peek_limit=peek_limit):
            continue
        # Full query_data / other tools are not "exploration-only"
        # (full requery → KIND_REPEATED_QUERY).
        return False
    return True


def should_break_exploration_thrash(
    recent_exploration_flags: list[bool],
    *,
    window: int,
) -> bool:
    if len(recent_exploration_flags) < window:
        return False
    tail = recent_exploration_flags[-window:]
    return all(tail)


def build_oscillation_event(
    kind: str,
    *,
    soft: bool,
) -> OscillationEvent:
    if kind == KIND_AGG_ERROR_RETRY:
        return OscillationEvent(
            kind=kind,
            soft=soft,
            title="数据链进度提醒：聚合绑定反复失败" if soft else "数据链熔断：聚合绑定死循环",
            progress_lines=[
                "已多次对同一类错误重试 aggregate_data（缺 input / 跨轮 ref / 口径绑错）。",
                "继续原样重试不会推进分析。",
            ],
            next_method_lines=[
                "请探索新方法：选 grain=row 的 dataset_id，显式传入 aggregate_data.input。",
                "可短探 list_datasets 只取 id；随后必须聚合，勿空转同一错误。",
                "若口径变了：先 query_data（新 where/班级），再聚合。",
            ],
        )
    if kind == KIND_REPEATED_QUERY:
        return OscillationEvent(
            kind=kind,
            soft=soft,
            title="数据链进度提醒：相同查询反复执行" if soft else "数据链熔断：重复全量查询",
            progress_lines=[
                "同一 resource/班级/周次的 query_data 已重复执行。",
                "磁盘上应已有可复用的 dataset_id（看 system 中的数据集目录）。",
            ],
            next_method_lines=[
                "请探索新方法：对已有 dataset_id 做 aggregate_data（正确率 sum(score)/sum(full_score) 或 mean(score_rate)；排名 order_by+limit）。",
                "缺满分列：enrich_data(lookup=title_info, on=title_ID, rename score→full_score) 再聚合。",
                "允许短探 list_datasets 取 id；目标仍是聚合/挂列，不是再全量 query。",
            ],
        )
    if kind == KIND_EXPLORATION_THRASH:
        return OscillationEvent(
            kind=kind,
            soft=soft,
            title="数据链进度提醒：探索未落到新方法" if soft else "数据链熔断：探索动作震荡",
            progress_lines=[
                "当前仍在 inspect_schema / read_file / list_datasets / 小 limit 窥探 / 改 todo。",
                "探索阶段应尽快落到可交付结果的方法；继续空探不会产生正确率或排名。",
            ],
            next_method_lines=[
                "请落到新方法：aggregate_data(已有 dataset_id, order_by+limit) 或 enrich_data 后再聚合。",
                "短探够了就停：同一 resource 不必反复 inspect；registry/catalog 不必反复 read_file。",
                "下一跳不要再只做窥探或改 todo。",
            ],
        )
    # KIND_PREVIEW_THRASH
    return OscillationEvent(
        kind=kind,
        soft=soft,
        title="数据链进度提醒：预览截断后的探索卡住了" if soft else "数据链熔断：预览截断反复重扫",
        progress_lines=[
            "已对同一聚合口径多次得到结果；预览行数受限是工具预算，不是「少了 N 人」。",
            "全量聚合表在 result_ref；继续全量 query_data 不会解决排名问题。",
        ],
        next_method_lines=[
            "请探索新方法 A：aggregate_data(同一 dataset_id, order_by+limit) 取最低/最高 K。",
            "或新方法 B：换 dimensions/指标再聚合（新问题）。",
            "不要因 truncated 再全量 query；短探后必须落到 order_by+limit。",
        ],
    )


def format_oscillation_hint(event: OscillationEvent) -> str:
    lines = [f"**{event.title}**（kind={event.kind}）", "", "进度："]
    lines.extend(f"- {x}" for x in event.progress_lines)
    lines.append("")
    lines.append("请换方法继续（本提示不是终点）：" if event.soft else "已熔断本轮空转；请用下列新方法在下一轮继续：")
    lines.extend(f"- {x}" for x in event.next_method_lines)
    return "\n".join(lines)
