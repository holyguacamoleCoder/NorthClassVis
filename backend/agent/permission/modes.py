from enum import Enum


class CapabilityMode(str, Enum):
    CONSULT = "consult"
    ANALYZE = "analyze"
    PRODUCE = "produce"


# consult：探查与目录浏览，不暴露 read_file（避免与「勿读原始 CSV」冲突、减少无效调用）
CONSULT_TOOLS = frozenset({"list_files", "load_skill", "load_reference", "inspect_schema", "get_current_filter_context"})
# analyze/produce：可读 meta、reports 等文本；原始 CSV 仍由 permission 路径策略拒绝
FILE_READ_TOOLS = frozenset({"read_file"})
DATA_INSPECT_TOOLS = frozenset({
    "inspect_schema",
    "list_datasets",
    "resolve_dataset_binding",
})
DATA_QUERY_TOOLS = frozenset({"query_data", "aggregate_data"})
ADAPTER_TOOLS = frozenset({"get_current_filter_context", "build_visual_links"})
SESSION_TOOLS = frozenset({"todo_write", "compact", "memory", "save_memory"})
WRITE_TOOLS = frozenset({"write_file", "edit_file"})
REPORT_REVIEW_TOOLS = frozenset({"review_report"})
SUBAGENT_TOOLS = frozenset({"run_subagent"})

MODE_TOOL_ALLOWLIST: dict[CapabilityMode, frozenset[str]] = {
    CapabilityMode.CONSULT: CONSULT_TOOLS,
    CapabilityMode.ANALYZE: FILE_READ_TOOLS | {"list_files", "load_skill", "load_reference"}
    | DATA_INSPECT_TOOLS
    | DATA_QUERY_TOOLS
    | SESSION_TOOLS
    | SUBAGENT_TOOLS
    | ADAPTER_TOOLS,
    CapabilityMode.PRODUCE: FILE_READ_TOOLS | {"list_files", "load_skill", "load_reference"}
    | DATA_INSPECT_TOOLS
    | DATA_QUERY_TOOLS
    | SESSION_TOOLS
    | WRITE_TOOLS
    | REPORT_REVIEW_TOOLS
    | SUBAGENT_TOOLS
    | ADAPTER_TOOLS,
}
