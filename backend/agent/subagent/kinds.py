"""Sub-agent kinds, tool allowlists, and capability modes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from permission.modes import CapabilityMode


class SubAgentKind(str, Enum):
    DATA_ANALYST = "data_analyst"
    REPORT_WRITER = "report_writer"
    REPORT_REVIEWER = "report_reviewer"


@dataclass(frozen=True)
class SubAgentKindConfig:
    kind: SubAgentKind
    label: str
    capability_mode: CapabilityMode
    max_turns: int
    max_tokens: int
    tools: frozenset[str]


_SHARED_ANALYZE = frozenset({
    "inspect_schema",
    "query_data",
    "aggregate_data",
    "list_datasets",
    "resolve_dataset_binding",
    "get_current_filter_context",
    "build_visual_links",
    "list_files",
    "read_file",
})

_SHARED_PRODUCE_WRITE = frozenset({
    "load_skill",
    "load_reference",
    "read_file",
    "list_files",
    "write_file",
    "edit_file",
    "get_current_filter_context",
    "build_visual_links",
    "review_report",
})

KIND_CONFIGS: dict[SubAgentKind, SubAgentKindConfig] = {
    SubAgentKind.DATA_ANALYST: SubAgentKindConfig(
        kind=SubAgentKind.DATA_ANALYST,
        label="数据侦察",
        capability_mode=CapabilityMode.ANALYZE,
        max_turns=12,
        max_tokens=6144,
        tools=_SHARED_ANALYZE,
    ),
    SubAgentKind.REPORT_WRITER: SubAgentKindConfig(
        kind=SubAgentKind.REPORT_WRITER,
        label="报告写作",
        capability_mode=CapabilityMode.PRODUCE,
        max_turns=16,
        max_tokens=8192,
        tools=_SHARED_PRODUCE_WRITE,
    ),
    SubAgentKind.REPORT_REVIEWER: SubAgentKindConfig(
        kind=SubAgentKind.REPORT_REVIEWER,
        label="报告修订",
        capability_mode=CapabilityMode.PRODUCE,
        max_turns=6,
        max_tokens=4096,
        tools=frozenset({
            "review_report",
            "read_file",
            "list_files",
            "edit_file",
            "get_current_filter_context",
        }),
    ),
}


def resolve_kind(raw: str) -> SubAgentKind | None:
    text = (raw or "").strip().lower()
    for kind in SubAgentKind:
        if text == kind.value:
            return kind
    aliases = {
        "analyst": SubAgentKind.DATA_ANALYST,
        "query": SubAgentKind.DATA_ANALYST,
        "writer": SubAgentKind.REPORT_WRITER,
        "reviewer": SubAgentKind.REPORT_REVIEWER,
        "review": SubAgentKind.REPORT_REVIEWER,
    }
    return aliases.get(text)


def kind_config(kind: SubAgentKind) -> SubAgentKindConfig:
    return KIND_CONFIGS[kind]


def list_subagent_kinds() -> list[dict[str, str]]:
    return [
        {"id": cfg.kind.value, "label": cfg.label, "mode": cfg.capability_mode.value}
        for cfg in KIND_CONFIGS.values()
    ]


def filter_subagent_tools(tool_schemas: list, kind: SubAgentKind) -> list:
    allowed = KIND_CONFIGS[kind].tools
    out: list = []
    for schema in tool_schemas:
        name = schema.get("function", {}).get("name")
        if name in allowed:
            out.append(schema)
    return out
