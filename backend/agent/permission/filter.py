from .modes import MODE_TOOL_ALLOWLIST, CapabilityMode


def filter_tools(tool_schemas: list, mode: CapabilityMode) -> list:
    allowed = MODE_TOOL_ALLOWLIST.get(mode, frozenset())
    filtered = []
    for schema in tool_schemas:
        name = schema.get("function", {}).get("name")
        if name in allowed:
            filtered.append(schema)
    return filtered
