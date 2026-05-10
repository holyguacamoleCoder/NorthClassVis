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

from .todo_write import TODO_MANAGER_SCHEMA

TOOLS = BASE_TOOLS + [
    TODO_MANAGER_SCHEMA,
]