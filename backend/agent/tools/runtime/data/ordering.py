"""Ensure query_data runs before aggregate_data within a batch."""

from __future__ import annotations

from typing import Any


def partition_tool_calls_for_data_pipeline(
    tool_calls: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """先执行 query_data（写入内存+硬盘），再执行其余（含 aggregate）。"""
    queries: list[dict[str, Any]] = []
    rest: list[dict[str, Any]] = []
    for call in tool_calls:
        if call.get("name") == "query_data":
            queries.append(call)
        else:
            rest.append(call)
    return queries, rest
