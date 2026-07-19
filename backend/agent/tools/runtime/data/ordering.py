"""Ensure query → enrich → aggregate order within a batch."""

from __future__ import annotations

from typing import Any


def partition_tool_calls_for_data_pipeline(
    tool_calls: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """先 query_data，再 enrich_data，最后其余（含 aggregate）。"""
    queries: list[dict[str, Any]] = []
    enrichs: list[dict[str, Any]] = []
    rest: list[dict[str, Any]] = []
    for call in tool_calls:
        name = call.get("name")
        if name == "query_data":
            queries.append(call)
        elif name == "enrich_data":
            enrichs.append(call)
        else:
            rest.append(call)
    return queries, enrichs + rest
