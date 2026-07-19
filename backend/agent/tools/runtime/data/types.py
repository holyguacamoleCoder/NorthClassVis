"""Data tool chain types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DATA_CHAIN_TOOLS = frozenset(
    {
        "query_data",
        "enrich_data",
        "aggregate_data",
        "inspect_schema",
        "list_datasets",
        "resolve_dataset_binding",
    }
)

ADAPTER_CONTEXT_TOOLS = frozenset(
    {
        "get_current_filter_context",
        "build_visual_links",
    }
)


@dataclass
class AggregateBinding:
    result_ref: str | None = None
    dataset_id: str | None = None
    error: str | None = None
    decision: str | None = None
    corrected: bool = False
    corrected_from: str | None = None
    auto_input: bool = False
    trace: dict[str, Any] | None = None
