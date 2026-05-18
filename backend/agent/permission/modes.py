from enum import Enum


class CapabilityMode(str, Enum):
    CONSULT = "consult"
    ANALYZE = "analyze"
    PRODUCE = "produce"


READ_ONLY_TOOLS = frozenset({"read_file", "list_files", "load_skill"})
SESSION_TOOLS = frozenset({"todo_write", "compact"})
WRITE_TOOLS = frozenset({"write_file", "edit_file"})

MODE_TOOL_ALLOWLIST: dict[CapabilityMode, frozenset[str]] = {
    CapabilityMode.CONSULT: READ_ONLY_TOOLS,
    CapabilityMode.ANALYZE: READ_ONLY_TOOLS | SESSION_TOOLS,
    CapabilityMode.PRODUCE: READ_ONLY_TOOLS | SESSION_TOOLS | WRITE_TOOLS,
}
