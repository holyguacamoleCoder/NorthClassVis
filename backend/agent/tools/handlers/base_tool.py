import subprocess
from pathlib import Path, PurePosixPath

from common.paths import DATA_DIR
from permission.paths import resolve_data_relative_path

MAX_OUTPUT_LENGTH = 50000
BLOCKED_WRITE_PATTERNS = ("out-file", "set-content", "add-content", ">")
WORKSPACE_PATH_ERROR = (
    "Error: Path must stay within data workspace (use paths relative to data/ only). "
    "| Next: use paths like reports/… or exports/… under data/"
)
HIDDEN_PATH_ERROR = (
    "Error: Hidden or agent-governance paths under data/ are not accessible via tools. "
    "| Next: write deliverables under reports/ or exports/"
)
_WRITE_CONTENT_WARN_BYTES = 512_000


def _safe_path(path: str) -> Path:
    normalized = resolve_data_relative_path(path)
    for part in PurePosixPath(normalized).parts:
        if part.startswith(".") or part == ".agent":
            raise ValueError("hidden or governance path segment")
    resolved = (DATA_DIR / normalized).resolve()
    if not resolved.is_relative_to(DATA_DIR.resolve()):
        raise ValueError(f"Path {resolved} escape from DATA_DIR workspace")
    return resolved


def _format_tool_error(exc: Exception, path: str | None = None) -> str:
    if isinstance(exc, ValueError) and "governance path segment" in str(exc):
        return HIDDEN_PATH_ERROR
    if isinstance(exc, ValueError) and (
        "escape from DATA_DIR" in str(exc) or "outside data workspace" in str(exc)
    ):
        return WORKSPACE_PATH_ERROR
    if path:
        return f"Error: {exc} ({path})"
    return f"Error: {exc}"


def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if not command or not isinstance(command, str):
        return "Error: Empty or invalid command"
    if any(item in command for item in dangerous):
        return "Error: Dangerous command blocked"
    lowered = command.lower()
    if any(token in lowered for token in BLOCKED_WRITE_PATTERNS):
        has_utf8_flag = ("-encoding utf8" in lowered) or ("-encoding utf-8" in lowered)
        if not has_utf8_flag:
            return (
                "Error: Shell file writing is blocked unless UTF-8 encoding is explicit. "
                "Use write_file/edit_file tools, or add -Encoding utf8."
            )

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=DATA_DIR,
            capture_output=True,
            text=True,
            timeout=120,
        )
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        output = (stdout + stderr).strip()
        return output[:MAX_OUTPUT_LENGTH] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"
    except (FileNotFoundError, OSError) as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error: {e}"


def run_read_file(path: str, limit: int | None = None) -> str:
    try:
        fp = _safe_path(path)
        text = fp.read_text(encoding="utf-8")
        lines = text.splitlines()
        total_lines = len(lines)
        truncated_lines = bool(limit and total_lines > limit)
        if truncated_lines:
            lines = lines[:limit] + [f"... ({total_lines - limit} more lines)"]
        body = "\n".join(lines)
        char_truncated = len(body) > MAX_OUTPUT_LENGTH
        if char_truncated:
            body = body[:MAX_OUTPUT_LENGTH]
        header = (
            f"[Read OK: path={path}, lines={min(total_lines, limit or total_lines)}, "
            f"truncated={truncated_lines or char_truncated}]\n"
        )
        suffix = ""
        if char_truncated:
            suffix = "\n[Truncated: use a smaller limit or query_data for tabular data]"
        return header + body + suffix
    except FileNotFoundError:
        return (
            f"Error: File not found: {path} | Next: list_files path=\"reports\" "
            f"or list_files path=\".\""
        )
    except UnicodeDecodeError:
        return (
            f"Error: File is not valid UTF-8: {path} | Next: do not read binary files; "
            "use query_data for tabular academic data"
        )
    except ValueError as e:
        return _format_tool_error(e, path)
    except Exception as e:
        return _format_tool_error(e, path)


def run_list_files(path: str = ".", recursive: bool = False, limit: int = 200) -> str:
    try:
        target_dir = _safe_path(path)
        if not target_dir.exists():
            return (
                f"Error: Path not found: {path} | Next: list_files path=\".\" "
                f"or list_files path=\"reports\""
            )
        if not target_dir.is_dir():
            return (
                f"Error: Not a directory: {path} | Next: list_files on parent directory "
                "or read_file if targeting a file"
            )

        entries: list[str] = []
        if recursive:
            for p in target_dir.rglob("*"):
                rel_parts = p.relative_to(target_dir).parts
                if any(part.startswith(".") for part in rel_parts):
                    continue
                rel = p.relative_to(target_dir).as_posix()
                entries.append(f"{rel}/" if p.is_dir() else rel)
        else:
            for p in target_dir.iterdir():
                name = p.name
                if name.startswith("."):
                    continue
                entries.append(f"{name}/" if p.is_dir() else name)

        entries.sort()
        total = len(entries)
        truncated = limit > 0 and total > limit
        if truncated:
            shown = entries[:limit]
            shown.append(f"... ({total - limit} more entries)")
            entries = shown
        header = f"[List: root={path}, count={total}, truncated={truncated}]\n"
        body = "\n".join(entries) if entries else "(empty directory)"
        return header + body
    except ValueError as e:
        return _format_tool_error(e, path)
    except Exception as e:
        return _format_tool_error(e, path)


def run_write_file(path: str, content: str) -> str:
    try:
        fp = _safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        existed = fp.exists()
        fp.write_text(content, encoding="utf-8", newline="\n")
        action = "overwritten" if existed else "created"
        msg = f"[Write OK: path={path}, bytes={len(content)}, {action}]"
        if len(content) > _WRITE_CONTENT_WARN_BYTES:
            msg += (
                f"\n[Warning: large write ({len(content)} chars); "
                "prefer concise markdown reports]"
            )
        return msg
    except ValueError as e:
        return _format_tool_error(e, path)
    except Exception as e:
        return _format_tool_error(e, path)


def run_edit_file(path: str, old_text: str, new_text: str) -> str:
    try:
        fp = _safe_path(path)
        content = fp.read_text(encoding="utf-8")
        if old_text not in content:
            return (
                f"Error: Text not found in {path} | Next: read_file path=\"{path}\" "
                "to copy an exact old_text snippet"
            )
        fp.write_text(content.replace(old_text, new_text, 1), encoding="utf-8", newline="\n")
        return f"[Edit OK: path={path}]"
    except UnicodeDecodeError:
        return (
            f"Error: File is not valid UTF-8: {path} | Next: do not read binary files; "
            "use query_data for tabular academic data"
        )
    except ValueError as e:
        return _format_tool_error(e, path)
    except Exception as e:
        return _format_tool_error(e, path)
