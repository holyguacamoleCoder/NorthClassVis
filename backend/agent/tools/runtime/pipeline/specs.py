"""Tool parameter specs for repair — derived from definitions.manifest."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...definitions.manifest import MANIFEST, ToolDefinition


@dataclass(frozen=True)
class ToolSpec:
    properties: dict[str, Any]
    required: frozenset[str]
    defaults: dict[str, Any]
    arg_aliases: dict[str, str]


def _spec_from_definition(defn: ToolDefinition) -> ToolSpec:
    props = defn.parameters.get("properties") or {}
    if not isinstance(props, dict):
        props = {}
    schema_defaults = {
        k: v["default"]
        for k, v in props.items()
        if isinstance(v, dict) and "default" in v
    }
    defaults = {**defn.defaults, **schema_defaults}
    return ToolSpec(
        properties=props,
        required=defn.required_params(),
        defaults=defaults,
        arg_aliases=dict(defn.arg_aliases),
    )


def build_tool_specs(
    manifest: tuple[ToolDefinition, ...] | None = None,
) -> dict[str, ToolSpec]:
    specs: dict[str, ToolSpec] = {}
    for defn in manifest or MANIFEST:
        specs[defn.name] = _spec_from_definition(defn)
    return specs


TOOL_SPECS: dict[str, ToolSpec] = build_tool_specs()
