BASE_TOOLS = [
    # {
    #     "type": "function",
    #     "function": {
    #         "name": "bash",
    #         "description": "Run a shell command in the current workspace.",
    #         "parameters": {
    #             "type": "object",
    #             "properties": {"command": {"type": "string"}},
    #             "required": ["command"],
    #         },
    #     },
    # },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read text under meta/, reports/, or exports/ (analyze/produce only). "
                "Never use for Data_*.csv or Data_SubmitRecord/; use inspect_schema/query_data instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files/directories under data workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "recursive": {"type": "boolean"},
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write to a file in the current workspace.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit a file in the current workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_text": {"type": "string"},
                    "new_text": {"type": "string"},
                },
                "required": ["path", "old_text", "new_text"],
            },
        },
    },
]

COMPACT_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "compact",
        "description": (
            "Summarize earlier conversation so work can continue in a smaller context. "
            "Use when the thread is long or you need to refocus."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "focus": {
                    "type": "string",
                    "description": "Optional focus to preserve in the summary.",
                },
            },
        },
    },
}

from ..handlers.todo_write import TODO_MANAGER_SCHEMA

LOAD_SKILL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "load_skill",
        "description": (
            "Load the full instructions for a named skill into the current context. "
            "Use before generating reports, analyzing CSV data, or other specialized work."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Skill name from the available skills list in the system prompt.",
                },
            },
            "required": ["name"],
        },
    },
}

SAVE_MEMORY_SCHEMA = {
    "type": "function",
    "function": {
        "name": "save_memory",
        "description": "Save a persistent memory that survives across sessions.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Short identifier (e.g. prefer_tabs, report_style)",
                },
                "description": {
                    "type": "string",
                    "description": "One-line summary of what this memory captures",
                },
                "type": {
                    "type": "string",
                    "enum": ["user", "feedback", "project", "reference"],
                    "description": (
                        "user=preferences, feedback=corrections, "
                        "project=non-obvious conventions, reference=external pointers"
                    ),
                },
                "content": {
                    "type": "string",
                    "description": "Full memory content (multi-line OK)",
                },
            },
            "required": ["name", "description", "type", "content"],
        },
    },
}

INSPECT_SCHEMA_TOOL = {
    "type": "function",
    "function": {
        "name": "inspect_schema",
        "description": (
            "Inspect a logical data resource: column names, types, sample rows, "
            "and estimated row count. Use before query_data."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "resource": {
                    "type": "string",
                    "description": "Logical resource id from resource_registry.yaml",
                },
                "class": {"type": "string", "description": "Single class for submit_record"},
                "classes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Class list for derived resources",
                },
                "majors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional major filter",
                },
            },
            "required": ["resource"],
        },
    },
}

QUERY_DATA_TOOL = {
    "type": "function",
    "function": {
        "name": "query_data",
        "description": (
            "Primary tool for class/student/submit analysis. Filter, project, group, sort, "
            "and limit a logical resource (e.g. submit_record_joined with classes=['Class1']). "
            "Prefer over read_file on Data_*.csv. Returns TabularResult JSON "
            "(preview rows; full data via meta.result_ref when truncated)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "resource": {"type": "string"},
                "select": {"type": "array", "items": {"type": "string"}},
                "where": {
                    "type": "object",
                    "description": "Safe DSL: {op, field, value} or {op: and, conditions: [...]}",
                },
                "filter": {
                    "type": "object",
                    "description": "Alias for where (deprecated; prefer where)",
                },
                "group_by": {"type": "array", "items": {"type": "string"}},
                "order_by": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {"type": "string"},
                            "dir": {"type": "string", "enum": ["asc", "desc"]},
                        },
                    },
                },
                "limit": {"type": "integer"},
                "class": {"type": "string"},
                "classes": {"type": "array", "items": {"type": "string"}},
                "majors": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["resource"],
        },
    },
}

AGGREGATE_DATA_TOOL = {
    "type": "function",
    "function": {
        "name": "aggregate_data",
        "description": (
            "Aggregate metrics over a prior query result_ref or small inline rows. "
            "Returns TabularResult JSON."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "input": {
                    "type": "object",
                    "description": "{result_ref} or {schema, rows} inline",
                },
                "metrics": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "op": {
                                "type": "string",
                                "enum": ["count", "sum", "mean", "min", "max"],
                            },
                            "field": {"type": "string"},
                            "as": {"type": "string"},
                        },
                        "required": ["op"],
                    },
                },
                "dimensions": {"type": "array", "items": {"type": "string"}},
                "window": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string"},
                        "size": {"type": "integer"},
                    },
                },
                "resource": {
                    "type": "string",
                    "description": "Optional resource id for meta when using inline input",
                },
            },
            "required": ["input", "metrics"],
        },
    },
}

DATA_TOOLS = [INSPECT_SCHEMA_TOOL, QUERY_DATA_TOOL, AGGREGATE_DATA_TOOL]

TOOLS = BASE_TOOLS + DATA_TOOLS + [
    TODO_MANAGER_SCHEMA,
    COMPACT_TOOL_SCHEMA,
    LOAD_SKILL_SCHEMA,
    SAVE_MEMORY_SCHEMA,
]