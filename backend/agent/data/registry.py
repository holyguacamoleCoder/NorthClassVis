from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import yaml

from .derived import build_submit_record_joined, build_week_aggregation
from .exceptions import InvalidParameterError, UnknownResourceError
from .limits import QueryLimits
from .loaders import (
    load_student_info,
    load_submit_record,
    load_title_info,
    project_data_dir,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_REGISTRY_PATH = _PROJECT_ROOT / "data" / "meta" / "resource_registry.yaml"

_DERIVED_LOADERS: dict[str, Callable[..., Any]] = {
    "build_submit_record_joined": build_submit_record_joined,
    "build_week_aggregation": build_week_aggregation,
}


@dataclass(frozen=True)
class ResolvedResource:
    resource_id: str
    kind: str
    metadata: dict
    load: Callable[..., Any]

    @property
    def schema_columns(self) -> list[str]:
        cols = self.metadata.get("columns") or self.metadata.get("output_columns")
        if cols:
            return list(cols)
        if self.kind == "csv" and "path_pattern" in self.metadata:
            return list(self.metadata.get("columns") or [])
        return []


@lru_cache(maxsize=1)
def _load_registry_document(registry_path: str | None = None) -> dict:
    path = Path(registry_path) if registry_path else _DEFAULT_REGISTRY_PATH
    if not path.is_file():
        raise FileNotFoundError(f"resource registry 不存在: {path}")
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def get_registry_defaults(registry_path: str | None = None) -> dict:
    doc = _load_registry_document(registry_path)
    return doc.get("defaults") or {}


def list_resource_ids(registry_path: str | None = None) -> list[str]:
    doc = _load_registry_document(registry_path)
    resources = doc.get("resources") or {}
    return sorted(resources.keys())


def resolve(
    resource_id: str,
    *,
    data_dir: Path | None = None,
    registry_path: str | None = None,
    **params: Any,
) -> ResolvedResource:
    """解析 logical resource id → 元数据 + loader callable。"""
    doc = _load_registry_document(registry_path)
    resources = doc.get("resources") or {}
    if resource_id not in resources:
        raise UnknownResourceError(resource_id)

    entry = dict(resources[resource_id])
    kind = entry.get("kind", "csv")
    data_dir = project_data_dir(data_dir)

    if kind == "csv":
        path_pattern = entry["path_pattern"]

        def _load_csv(**load_params: Any):
            from .loaders import load_csv_resource

            merged = {**params, **load_params}
            if resource_id == "submit_record":
                class_name = merged.get("class")
                if not class_name:
                    raise InvalidParameterError(
                        "submit_record 需要参数 class",
                        param="class",
                    )
                return load_submit_record(class_name, data_dir)
            return load_csv_resource(path_pattern, data_dir, **merged)

        if resource_id == "student_info":
            load_fn = lambda **kw: load_student_info(data_dir)  # noqa: E731
        elif resource_id == "title_info":
            load_fn = lambda **kw: load_title_info(data_dir)  # noqa: E731
        else:
            load_fn = _load_csv

    elif kind == "derived":
        loader_name = entry.get("loader")
        loader_fn = _DERIVED_LOADERS.get(loader_name)
        if loader_fn is None:
            raise InvalidParameterError(f"未注册的 derived loader: {loader_name!r}")

        def load_fn(**load_params: Any):
            merged = {**params, **load_params}
            if "classes" not in merged and "class" in merged:
                merged["classes"] = [merged.pop("class")]
            if resource_id == "submit_record_joined":
                if "classes" not in merged:
                    raise InvalidParameterError(
                        "submit_record_joined 需要参数 classes",
                        param="classes",
                    )
                return loader_fn(
                    merged["classes"],
                    merged.get("majors"),
                    data_dir=data_dir,
                )
            if resource_id == "week_aggregation":
                if "classes" not in merged:
                    raise InvalidParameterError(
                        "week_aggregation 需要参数 classes",
                        param="classes",
                    )
                return loader_fn(
                    merged["classes"],
                    majors=merged.get("majors"),
                    student_ids=merged.get("student_ids"),
                    week_range=merged.get("week_range"),
                    data_dir=data_dir,
                )
            return loader_fn(**merged, data_dir=data_dir)

    else:
        raise InvalidParameterError(f"不支持的 resource kind: {kind!r}")

    return ResolvedResource(
        resource_id=resource_id,
        kind=kind,
        metadata=entry,
        load=load_fn,
    )


def default_limits(registry_path: str | None = None) -> QueryLimits:
    return QueryLimits.from_registry_defaults(get_registry_defaults(registry_path))
