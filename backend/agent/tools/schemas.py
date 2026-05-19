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
            "description": "Read a file in the current workspace.",
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

from .todo_write import TODO_MANAGER_SCHEMA

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

TOOLS = BASE_TOOLS + [
    TODO_MANAGER_SCHEMA,
    COMPACT_TOOL_SCHEMA,
    LOAD_SKILL_SCHEMA,
    SAVE_MEMORY_SCHEMA,
]