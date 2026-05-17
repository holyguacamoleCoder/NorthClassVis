import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]  # NorthClassVision
DATA_DIR = BASE_DIR / "data"
MAX_OUTPUT_LENGTH = 50000
BLOCKED_WRITE_PATTERNS = ("out-file", "set-content", "add-content", ">")
WORKSPACE_PATH_ERROR = (
    "Error: Path must stay within data workspace (use paths relative to data/ only)."
)


def _safe_path(path: str) -> Path:
    resolved = (DATA_DIR / path).resolve()
    if not resolved.is_relative_to(DATA_DIR):
        raise ValueError(f"Path {resolved} escape from DATA_DIR workspace")
    return resolved


def _format_tool_error(exc: Exception, path: str | None = None) -> str:
    if isinstance(exc, ValueError) and "escape from DATA_DIR" in str(exc):
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
        if limit and len(lines) > limit:
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)[:MAX_OUTPUT_LENGTH]
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except UnicodeDecodeError:
        return f"Error: File is not valid UTF-8: {path}"
    except ValueError as e:
        return _format_tool_error(e, path)
    except Exception as e:
        return _format_tool_error(e, path)


def run_list_files(path: str = ".", recursive: bool = False, limit: int = 200) -> str:
    try:
        target_dir = _safe_path(path)
        if not target_dir.exists():
            return f"Error: Path not found: {path}"
        if not target_dir.is_dir():
            return f"Error: Not a directory: {path}"

        entries: list[str] = []
        if recursive:
            for p in target_dir.rglob("*"):
                rel = p.relative_to(target_dir).as_posix()
                entries.append(f"{rel}/" if p.is_dir() else rel)
        else:
            for p in target_dir.iterdir():
                name = p.name
                entries.append(f"{name}/" if p.is_dir() else name)

        entries.sort()
        if limit > 0 and len(entries) > limit:
            shown = entries[:limit]
            shown.append(f"... ({len(entries) - limit} more entries)")
            entries = shown
        return "\n".join(entries) if entries else "(empty directory)"
    except ValueError as e:
        return _format_tool_error(e, path)
    except Exception as e:
        return _format_tool_error(e, path)


def run_write_file(path: str, content: str) -> str:
    try:
        fp = _safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8", newline="\n")
        return f"Wrote {len(content)} bytes to {path}"
    except ValueError as e:
        return _format_tool_error(e, path)
    except Exception as e:
        return _format_tool_error(e, path)


def run_edit_file(path: str, old_text: str, new_text: str) -> str:
    try:
        fp = _safe_path(path)
        content = fp.read_text(encoding="utf-8")
        if old_text not in content:
            return f"Error: Text not found in {path}"
        fp.write_text(content.replace(old_text, new_text, 1), encoding="utf-8", newline="\n")
        return f"Edited {path}"
    except UnicodeDecodeError:
        return f"Error: File is not valid UTF-8: {path}"
    except ValueError as e:
        return _format_tool_error(e, path)
    except Exception as e:
        return _format_tool_error(e, path)
