"""Aggregate input binding types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


# Rows above this strongly indicate a broad submit_record-style scan.
SLICE_MAX_ROWS = 500
# Intentional top-N / preview slices are usually this small.
PREVIEW_SLICE_ROWS = 50
# Auto-pick must beat explicit ref by this margin to silently correct.
CORRECTION_MARGIN = 1.5
CROSS_TURN_PENALTY = 100.0


class BindMode(str, Enum):
    AUTO = "auto"
    CHAIN = "chain"
    FRESH = "fresh"

    @classmethod
    def parse(cls, raw: str | None) -> BindMode:
        if not raw:
            return cls.AUTO
        try:
            return cls(str(raw).strip().lower())
        except ValueError:
            return cls.AUTO


@dataclass(frozen=True)
class BindingCandidate:
    result_ref: str
    result_rows: int
    user_turn: int
    query_limit: int | None = None
    rows_scanned: int | None = None
    dataset_id: str | None = None
    resource: str | None = None
    grain: str | None = None
    columns: list[str] | None = None
    parent_dataset_id: str | None = None

    @property
    def is_slice(self) -> bool:
        if self.query_limit is not None and self.query_limit > 0:
            return True
        scanned = self.rows_scanned or 0
        rows = self.result_rows
        # Preview truncation: scanned many rows but returned a small subset.
        if scanned > rows:
            return True
        if rows <= PREVIEW_SLICE_ROWS:
            return True
        return False

    @property
    def is_broad_scan(self) -> bool:
        if self.query_limit is not None and self.query_limit > 0:
            return False
        rows = self.result_rows
        scanned = self.rows_scanned or 0
        if rows > SLICE_MAX_ROWS:
            return True
        # Full scan: all matching rows returned (e.g. week_aggregation ~ students×weeks).
        if scanned > 0 and rows >= scanned:
            return True
        # Legacy rows without rows_scanned metadata: trust non-trivial unbounded results.
        if scanned == 0 and rows > PREVIEW_SLICE_ROWS:
            return True
        return False


@dataclass
class DatasetBindingDecision:
    scope: str
    dataset_id: str
    result_ref: str
    confidence: str = "medium"
    rationale: str = ""
    overrides_model_ref: bool = False
    resolver: str = "heuristic"
