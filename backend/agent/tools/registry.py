from typing import Callable

from .base_tool import run_bash, run_edit_file, run_list_files, run_read_file, run_write_file
from .compact import run_compact
from .load_skill import run_load_skill
from .todo_write import run_todo_write

CONCURRENCY_LIMIT = 10
CONCURRENCY_SAFE_TOOL = {"read_file", "list_files"}
CONCURRENCY_UNSAFE_TOOL = {"write_file", "edit_file"}

TOOL_DISPATCHER: dict[str, Callable[..., str]] = {
    # "bash": lambda **kwargs: run_bash(kwargs.get("command")),
    "read_file": lambda **kwargs: run_read_file(kwargs.get("path"), kwargs.get("limit")),
    "list_files": lambda **kwargs: run_list_files(
        kwargs.get("path", "."),
        kwargs.get("recursive", False),
        kwargs.get("limit", 200),
    ),
    "write_file": lambda **kwargs: run_write_file(kwargs.get("path"), kwargs.get("content")),
    "edit_file": lambda **kwargs: run_edit_file(
        kwargs.get("path"),
        kwargs.get("old_text"),
        kwargs.get("new_text"),
    ),
    "todo_write": lambda **kwargs: run_todo_write(kwargs.get("items")),
    "compact": lambda **kwargs: run_compact(kwargs.get("focus")),
    "load_skill": lambda **kwargs: run_load_skill(kwargs.get("name")),
}
