# Paths are relative to data/ (sandbox: tools.base_tool._safe_path).
# Write path policy lives here; mode_check only gates tool + capability mode.

from .paths import WRITE_ALLOW_PATTERNS, WRITE_DENY_PATTERNS

_DEFAULT_WRITE_ALLOW = [
    {"tool": tool, "path": pattern, "behavior": "allow"}
    for tool in ("write_file", "edit_file")
    for pattern in WRITE_ALLOW_PATTERNS
]

_DEFAULT_WRITE_DENY = [
    {"tool": tool, "path": pattern, "behavior": "deny"}
    for tool in ("write_file", "edit_file")
    for pattern in WRITE_DENY_PATTERNS
]

DEFAULT_RULES: list[dict] = [
    *_DEFAULT_WRITE_DENY,
    *_DEFAULT_WRITE_ALLOW,
    {"tool": "read_file", "path": "*", "behavior": "allow"},
    {"tool": "list_files", "path": "*", "behavior": "allow"},
    {"tool": "todo_write", "path": "*", "behavior": "allow"},
    {"tool": "compact", "path": "*", "behavior": "allow"},
]
