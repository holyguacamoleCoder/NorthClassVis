"""Agent Phase 1–2：逻辑数据资源、查询与聚合（库层）。"""

from .aggregate import AggregateSpec, execute_aggregate
from .filter_context import FilterContext
from .inspect import inspect_resource
from .limits import QueryLimits, apply_row_limit
from .query import PREVIEW_ROW_LIMIT, QuerySpec, execute_query
from .registry import ResolvedResource, default_limits, resolve
from .result_store import load_result, save_result
from .tabular import dataframe_to_tabular, validate_tabular_result

__all__ = [
    "AggregateSpec",
    "FilterContext",
    "PREVIEW_ROW_LIMIT",
    "QueryLimits",
    "QuerySpec",
    "ResolvedResource",
    "apply_row_limit",
    "dataframe_to_tabular",
    "default_limits",
    "execute_aggregate",
    "execute_query",
    "inspect_resource",
    "load_result",
    "resolve",
    "save_result",
    "validate_tabular_result",
]
