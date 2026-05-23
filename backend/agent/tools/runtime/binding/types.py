"""Aggregate input binding types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


# Rows at or below this are treated as intentional slices (top-N, preview).
SLICE_MAX_ROWS = 500
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

    @property
    def is_slice(self) -> bool:
        if self.query_limit is not None:
            return True
        return self.result_rows <= SLICE_MAX_ROWS

    @property
    def is_broad_scan(self) -> bool:
        if self.query_limit is not None:
            return False
        if self.result_rows > SLICE_MAX_ROWS:
            return True
        scanned = self.rows_scanned or 0
        return scanned > SLICE_MAX_ROWS and self.result_rows >= min(
            scanned, max(self.result_rows, SLICE_MAX_ROWS + 1)
        )


@dataclass
class DatasetBindingDecision:
    scope: str
    dataset_id: str
    result_ref: str
    confidence: str = "medium"
    rationale: str = ""
    overrides_model_ref: bool = False
    resolver: str = "heuristic"
