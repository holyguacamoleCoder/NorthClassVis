from typing import Callable

from ..handlers.base_tool import (
    run_bash,
    run_edit_file,
    run_list_files,
    run_read_file,
    run_write_file,
)
from ..handlers.compact import run_compact
from ..handlers.data_tools import run_aggregate_data, run_inspect_schema, run_query_data
from ..handlers.load_skill import run_load_skill
from ..handlers.save_memory import run_save_memory
from ..handlers.todo_write import run_todo_write

CONCURRENCY_LIMIT = 10
CONCURRENCY_SAFE_TOOL = {
    "read_file",
    "list_files",
    "inspect_schema",
    "query_data",
    "aggregate_data",
}
CONCURRENCY_UNSAFE_TOOL = {"write_file", "edit_file"}

TOOL_DISPATCHER: dict[str, Callable[..., str]] = {
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
    "save_memory": lambda **kwargs: run_save_memory(
        kwargs.get("name"),
        kwargs.get("description"),
        kwargs.get("type"),
        kwargs.get("content"),
    ),
    "inspect_schema": lambda **kwargs: run_inspect_schema(**kwargs),
    "query_data": lambda **kwargs: run_query_data(**kwargs),
    "aggregate_data": lambda **kwargs: run_aggregate_data(**kwargs),
}
