from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FilterContext:
    """Phase 3 get_current_filter_context 预留；Phase 1 由调用方显式传入。"""

    classes: tuple[str, ...] | None = None
    majors: tuple[str, ...] | None = None
    week_range: tuple[int, int] | None = None
    selected_student_ids: tuple[str, ...] | None = None

    def to_resolve_params(self) -> dict:
        params: dict = {}
        if self.classes:
            params["classes"] = list(self.classes)
        if self.majors:
            params["majors"] = list(self.majors)
        if self.week_range is not None:
            params["week_range"] = list(self.week_range)
        if self.selected_student_ids:
            params["student_ids"] = list(self.selected_student_ids)
        return params
