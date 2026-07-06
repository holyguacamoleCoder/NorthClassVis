from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

SourceType = Literal["session", "http_body", "env_default", "default"]

_CLASS_FILE_RE = re.compile(r"^SubmitRecord-(Class\d+)\.csv$", re.IGNORECASE)
_MESSAGE_CLASS_RE = re.compile(r"\bClass\d+\b", re.IGNORECASE)
_VALID_STUDENT_ID_RE = re.compile(r"^[0-9a-f]{16,24}$", re.I)
_PLACEHOLDER_STUDENT_RE = re.compile(
    r"^(student\d*|stu\d*|user\d*|example|dummy|test|placeholder|xxx+|\?+)$",
    re.I,
)


def is_placeholder_student_id(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    if text.startswith("<") and text.endswith(">"):
        return True
    if _PLACEHOLDER_STUDENT_RE.match(text):
        return True
    return text.lower() in ("student_id", "studentid", "unknown", "n/a", "na")


def is_valid_student_id(value: str) -> bool:
    return bool(_VALID_STUDENT_ID_RE.match(str(value or "").strip()))


def clean_student_ids(values: list[str] | tuple[str, ...] | None) -> list[str]:
    if not values:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        sid = str(raw or "").strip()
        if not sid or is_placeholder_student_id(sid) or not is_valid_student_id(sid):
            continue
        if sid in seen:
            continue
        seen.add(sid)
        out.append(sid)
    return out


def sample_typical_student_ids(
    classes: tuple[str, ...] | list[str],
    *,
    majors: tuple[str, ...] | list[str] | None = None,
    week_range: tuple[int, int] | None = None,
    limit: int = 3,
    data_dir: Path | None = None,
) -> list[str]:
    """Pick 2–3 representative student_IDs for WeekView (most submissions in scope)."""
    if not classes:
        return []
    try:
        from .loaders import load_student_info, load_submit_records

        df = load_submit_records(list(classes), data_dir=data_dir)
        if df.empty or "student_ID" not in df.columns:
            return []
        if week_range is not None and "week_index" in df.columns:
            lo, hi = week_range
            scoped = df[(df["week_index"] >= lo) & (df["week_index"] <= hi)]
            if not scoped.empty:
                df = scoped
        if majors:
            student_df = load_student_info(data_dir)
            if not student_df.empty and "major" in student_df.columns:
                allowed = set(
                    student_df[student_df["major"].isin(list(majors))]["student_ID"].astype(str)
                )
                df = df[df["student_ID"].astype(str).isin(allowed)]
        if df.empty:
            return []
        counts = df.groupby("student_ID").size().sort_values(ascending=False)
        return [str(sid) for sid in counts.head(max(1, limit)).index.tolist()]
    except Exception:
        return []

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


def _classes_mentioned_in_message(message: str | None) -> set[str]:
    if not message:
        return set()
    return {m.group(0) for m in _MESSAGE_CLASS_RE.finditer(message)}


def _normalize_explicit_classes(explicit: dict[str, Any]) -> set[str]:
    classes: set[str] = set()
    raw_class = explicit.get("class")
    if raw_class is not None and str(raw_class).strip():
        classes.add(str(raw_class).strip())
    for item in explicit.get("classes") or []:
        if item is not None and str(item).strip():
            classes.add(str(item).strip())
    return classes


def _students_present_in_classes(
    student_ids: tuple[str, ...] | list[str],
    classes: set[str],
    *,
    data_dir: Path | None = None,
) -> bool:
    if not student_ids or not classes:
        return False
    try:
        from .loaders import load_submit_records

        df = load_submit_records(sorted(classes), data_dir=data_dir)
        if df.empty or "student_ID" not in df.columns:
            return False
        present = set(df["student_ID"].astype(str))
        return any(str(sid) in present for sid in student_ids)
    except Exception:
        return True


def nav_scope_suppressed_reason(
    filter_context: "FilterContext",
    explicit: dict[str, Any],
    *,
    teacher_message: str | None = None,
    data_dir: Path | None = None,
) -> str | None:
    """
    When tool/query scope conflicts with Nav, teacher intent wins over panel selection.
    Returns a human-readable note if nav student_ids/majors must be ignored.
    """
    from session.ui_scope import teacher_has_selection_intent

    if explicit.get("student_ids"):
        return None

    explicit_classes = _normalize_explicit_classes(explicit)
    nav_classes = set(filter_context.classes or ())

    message_classes = _classes_mentioned_in_message(teacher_message)
    if message_classes and explicit_classes and not message_classes.intersection(explicit_classes):
        return (
            f"用户消息提及 {sorted(message_classes)}，查询为 {sorted(explicit_classes)}，"
            "已忽略面板选区（以用户消息/查询范围为准）"
        )

    if explicit_classes and nav_classes and not explicit_classes.intersection(nav_classes):
        return (
            f"查询班级 {sorted(explicit_classes)} 与面板班级 {sorted(nav_classes)} 不一致，"
            "已按查询班级全文分析（忽略面板选中的学生/专业）"
        )

    if explicit_classes and filter_context.selected_student_ids:
        if not _students_present_in_classes(
            filter_context.selected_student_ids,
            explicit_classes,
            data_dir=data_dir,
        ):
            return (
                "面板选中的学生不属于本次查询班级，已按查询班级全文分析"
            )

    if (
        explicit_classes
        and filter_context.selected_student_ids
        and not teacher_has_selection_intent(teacher_message)
    ):
        return (
            "查询指定班级且未限定 student_ids，教师未表达「所选学生」意图，"
            "已按班级全文分析（忽略面板局部选中）"
        )

    return None


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

    def effective_nav_scope_for_query(
        self,
        explicit: dict[str, Any],
        *,
        teacher_message: str | None = None,
        resource_id: str | None = None,
        data_dir: Path | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Nav resolve params to apply; omit student_ids/majors when teacher/query scope wins."""
        scoped = (
            self.resolve_params_for_resource(resource_id)
            if resource_id
            else self.to_resolve_params()
        )
        reason = nav_scope_suppressed_reason(
            self,
            explicit,
            teacher_message=teacher_message,
            data_dir=data_dir,
        )
        if not reason:
            return scoped, None
        trimmed = {k: v for k, v in scoped.items() if k not in ("student_ids", "majors")}
        return trimmed, reason

    def merge_resolve_params(
        self,
        explicit: dict[str, Any],
        *,
        resource_id: str | None = None,
        teacher_message: str | None = None,
        data_dir: Path | None = None,
        scope_notes: list[str] | None = None,
    ) -> dict[str, Any]:
        scoped, reason = self.effective_nav_scope_for_query(
            explicit,
            teacher_message=teacher_message,
            resource_id=resource_id,
            data_dir=data_dir,
        )
        if reason and scope_notes is not None:
            scope_notes.append(reason)
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
            typical = sample_typical_student_ids(
                self.classes or (),
                majors=self.majors,
                week_range=self.week_range,
                limit=3,
            )
            if typical:
                out["typical_student_ids"] = typical
                out["week_view_hint"] = (
                    "班级 WeekView / report-chart 请使用 typical_student_ids（2–3 人），"
                    "勿编造 student1 等占位符。"
                )
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
