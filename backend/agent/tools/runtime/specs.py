"""Tool parameter specs derived from OpenAI function schemas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..definitions.schemas import TOOLS

RUNTIME_DEFAULTS: dict[str, dict[str, Any]] = {
    "list_files": {"path": ".", "recursive": False, "limit": 200},
}


@dataclass(frozen=True)
class ToolSpec:
    properties: dict[str, Any]
    required: frozenset[str]
    defaults: dict[str, Any]


def _extract_tool_entry(entry: dict[str, Any]) -> tuple[str, ToolSpec] | None:
    fn = entry.get("function")
    if not isinstance(fn, dict):
        return None
    name = fn.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    params = fn.get("parameters") or {}
    if not isinstance(params, dict):
        params = {}
    props = params.get("properties") or {}
    if not isinstance(props, dict):
        props = {}
    req_raw = params.get("required") or []
    required = frozenset(str(k) for k in req_raw if isinstance(k, str))
    schema_defaults = {
        k: v["default"]
        for k, v in props.items()
        if isinstance(v, dict) and "default" in v
    }
    defaults = {**RUNTIME_DEFAULTS.get(name, {}), **schema_defaults}
    return name, ToolSpec(properties=props, required=required, defaults=defaults)


def build_tool_specs(tools: list[dict[str, Any]] | None = None) -> dict[str, ToolSpec]:
    specs: dict[str, ToolSpec] = {}
    for entry in tools or TOOLS:
        if not isinstance(entry, dict):
            continue
        parsed = _extract_tool_entry(entry)
        if parsed is None:
            continue
        specs[parsed[0]] = parsed[1]
    return specs


TOOL_SPECS: dict[str, ToolSpec] = build_tool_specs()
