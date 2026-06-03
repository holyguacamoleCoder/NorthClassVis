from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

SourceType = Literal["session", "http_body", "env_default", "default"]

_CLASS_FILE_RE = re.compile(r"^SubmitRecord-(Class\d+)\.csv$", re.IGNORECASE)


def _project_data_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "data"


def _coerce_str_list(value: Any) -> tuple[str, ...] | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() == "all":
            return None
        return (text,)
    if isinstance(value, (list, tuple)):
        items = [str(v).strip() for v in value if v is not None and str(v).strip()]
        if not items:
            return None
        if len(items) == 1 and items[0].lower() == "all":
            return None
        return tuple(items)
    text = str(value).strip()
    return (text,) if text else None


def _coerce_week_range(value: Any) -> tuple[int, int] | None:
    if value is None:
        return None
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",") if p.strip()]
        if len(parts) != 2:
            return None
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            return None
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            return int(value[0]), int(value[1])
        except (TypeError, ValueError):
            return None
    return None


def discover_default_classes(data_dir: Path | None = None) -> tuple[str, ...]:
    root = data_dir or _project_data_dir()
    submit_dir = root / "Data_SubmitRecord"
    if submit_dir.is_dir():
        found: list[str] = []
        for path in sorted(submit_dir.iterdir()):
            match = _CLASS_FILE_RE.match(path.name)
            if match:
                found.append(match.group(1))
        if found:
            return tuple(found)
    return ("Class1",)


@dataclass(frozen=True)
class FilterContext:
    """Nav / session analysis scope for query_data resolve params."""

    classes: tuple[str, ...] | None = None
    majors: tuple[str, ...] | None = None
    week_range: tuple[int, int] | None = None
    selected_student_ids: tuple[str, ...] | None = None
    source: SourceType = "default"
    defaults_applied: tuple[str, ...] = field(default_factory=tuple)

    def to_resolve_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if self.classes:
            params["classes"] = list(self.classes)
        if self.majors:
            params["majors"] = list(self.majors)
        if self.week_range is not None:
            params["week_range"] = list(self.week_range)
        if self.selected_student_ids:
            params["student_ids"] = list(self.selected_student_ids)
        return params

    def resolve_params_for_resource(self, resource_id: str) -> dict[str, Any]:
        """Scope params that loaders actually accept (avoid majors on student_info)."""
        raw = self.to_resolve_params()
        if resource_id in ("student_info", "title_info"):
            if raw.get("student_ids"):
                return {"student_ids": raw["student_ids"]}
            return {}
        if resource_id == "week_aggregation":
            out: dict[str, Any] = {}
            if raw.get("classes"):
                out["classes"] = raw["classes"]
            if raw.get("majors"):
                out["majors"] = raw["majors"]
            if raw.get("week_range") is not None:
                out["week_range"] = raw["week_range"]
            if raw.get("student_ids"):
                out["student_ids"] = raw["student_ids"]
            return out
        return dict(raw)

    def merge_resolve_params(
        self,
        explicit: dict[str, Any],
        *,
        resource_id: str | None = None,
    ) -> dict[str, Any]:
        scoped = (
            self.resolve_params_for_resource(resource_id)
            if resource_id
            else self.to_resolve_params()
        )
        merged = dict(explicit)
        for key, value in scoped.items():
            if key == "classes":
                if merged.get("class") or merged.get("classes"):
                    continue
            elif merged.get(key) is not None:
                continue
            merged[key] = value
        return merged

    def to_dict(self) -> dict[str, Any]:
        return {
            "classes": list(self.classes) if self.classes else None,
            "majors": list(self.majors) if self.majors else None,
            "week_range": list(self.week_range) if self.week_range is not None else None,
            "selected_student_ids": (
                list(self.selected_student_ids) if self.selected_student_ids else None
            ),
            "defaults_applied": list(self.defaults_applied),
            "source": self.source,
        }

    def to_summary_dict(
        self,
        *,
        include_student_ids: bool = False,
        preview_limit: int = 5,
    ) -> dict[str, Any]:
        """
        Compact scope for LLM prompts / default get_current_filter_context.
        Full ID lists are omitted unless include_student_ids=True.
        """
        ids = list(self.selected_student_ids) if self.selected_student_ids else []
        out: dict[str, Any] = {
            "classes": list(self.classes) if self.classes else None,
            "majors": list(self.majors) if self.majors else None,
            "week_range": list(self.week_range) if self.week_range is not None else None,
            "selected_student_count": len(ids),
            "defaults_applied": list(self.defaults_applied),
            "source": self.source,
            "scope_binding": "session",
        }
        if include_student_ids:
            out["selected_student_ids"] = ids or None
            return out

        out["selected_student_ids"] = None
        if not ids:
            return out

        if len(ids) <= preview_limit:
            out["selected_student_ids_preview"] = ids
        else:
            out["selected_student_ids_preview"] = ids[:preview_limit]
            out["selected_student_ids_truncated"] = True
        out["resolve_hint"] = (
            "完整学号列表请调用 get_current_filter_context(include_student_ids=true)；"
            "query_data / inspect_schema 已自动应用 Nav 选区 student_ids，通常无需展开列表。"
        )
        return out

    @classmethod
    def from_http_body(cls, body: dict[str, Any] | None) -> FilterContext | None:
        if not body:
            return None
        classes = _coerce_str_list(body.get("classes"))
        majors = _coerce_str_list(body.get("majors"))
        week_range = _coerce_week_range(body.get("week_range"))
        selected = _coerce_str_list(body.get("selected_student_ids"))
        if not any((classes, majors, week_range, selected)):
            return None
        return cls(
            classes=classes,
            majors=majors,
            week_range=week_range,
            selected_student_ids=selected,
            source="http_body",
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> FilterContext | None:
        if not data:
            return None
        classes = _coerce_str_list(data.get("classes"))
        majors = _coerce_str_list(data.get("majors"))
        week_range = _coerce_week_range(data.get("week_range"))
        selected = _coerce_str_list(data.get("selected_student_ids"))
        source = data.get("source") or "session"
        if source not in ("session", "http_body", "env_default", "default"):
            source = "session"
        defaults = tuple(str(x) for x in (data.get("defaults_applied") or []))
        if not any((classes, majors, week_range, selected)):
            return None
        return cls(
            classes=classes,
            majors=majors,
            week_range=week_range,
            selected_student_ids=selected,
            source=source,  # type: ignore[arg-type]
            defaults_applied=defaults,
        )

    @classmethod
    def from_env(cls) -> FilterContext | None:
        raw_classes = os.environ.get("AGENT_DEFAULT_CLASSES", "").strip()
        raw_majors = os.environ.get("AGENT_DEFAULT_MAJORS", "").strip()
        raw_week = os.environ.get("AGENT_DEFAULT_WEEK_RANGE", "").strip()
        if not any((raw_classes, raw_majors, raw_week)):
            return None
        return cls(
            classes=_coerce_str_list(raw_classes.split(",") if raw_classes else None),
            majors=_coerce_str_list(raw_majors.split(",") if raw_majors else None),
            week_range=_coerce_week_range(raw_week),
            source="env_default",
        )


def merge_http_context(
    existing: FilterContext | None,
    incoming: FilterContext | None,
) -> FilterContext | None:
    """Merge POST /messages context onto session scope (incoming wins per field)."""
    if incoming is None:
        return existing
    if existing is None:
        return incoming
    return FilterContext(
        classes=incoming.classes if incoming.classes is not None else existing.classes,
        majors=incoming.majors if incoming.majors is not None else existing.majors,
        week_range=(
            incoming.week_range if incoming.week_range is not None else existing.week_range
        ),
        selected_student_ids=(
            incoming.selected_student_ids
            if incoming.selected_student_ids is not None
            else existing.selected_student_ids
        ),
        source=incoming.source,
        defaults_applied=existing.defaults_applied or incoming.defaults_applied,
    )


def merge_defaults(
    ctx: FilterContext | None,
    *,
    data_dir: Path | None = None,
) -> FilterContext:
    """Fill missing classes from registry / filesystem when absent."""
    if ctx is not None and ctx.classes:
        return ctx
    default_classes = discover_default_classes(data_dir)
    applied = ("classes default from resource_registry / Data_SubmitRecord",)
    if ctx is None:
        return FilterContext(
            classes=default_classes,
            source="default",
            defaults_applied=applied,
        )
    return FilterContext(
        classes=ctx.classes or default_classes,
        majors=ctx.majors,
        week_range=ctx.week_range,
        selected_student_ids=ctx.selected_student_ids,
        source=ctx.source,
        defaults_applied=ctx.defaults_applied + applied if not ctx.classes else ctx.defaults_applied,
    )
