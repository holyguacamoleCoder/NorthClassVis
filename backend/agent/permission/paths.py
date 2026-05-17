"""Path policy for permission rules (sandbox: tools.base_tool._safe_path)."""

from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

DATA_DIR = Path(__file__).resolve().parents[3] / "data"

WRITABLE_SUBDIRS = ("reports", "exports")

# Used by rules.py and path policy checks (supports ** for nested paths).
WRITE_ALLOW_PATTERNS = tuple(f"{name}/**" for name in WRITABLE_SUBDIRS)
WRITE_DENY_PATTERNS = ("Data_*.csv",)


def normalize_path(path: str | None) -> str:
    raw = str(path or "").strip().replace("\\", "/").lstrip("./")
    if raw.startswith("data/"):
        raw = raw[5:]
    return raw


def to_data_relative_path(path: str | None) -> str:
    """
    Normalize tool path for permission checks: relative to data/, forward slashes.
    Accepts reports/foo, data/reports/foo, or absolute .../data/reports/foo.
    """
    raw = str(path or "").strip()
    if not raw:
        return ""

    candidate = Path(raw)
    if candidate.is_absolute():
        try:
            rel = candidate.resolve().relative_to(DATA_DIR.resolve())
            return rel.as_posix()
        except ValueError:
            return normalize_path(raw)

    return normalize_path(raw)


def path_matches_pattern(path: str, pattern: str) -> bool:
    """Match tool paths against rule patterns (* and reports/** style)."""
    normalized = to_data_relative_path(path)
    pat = pattern.replace("\\", "/")

    if pat == "*":
        return True

    if "**" in pat:
        if pat.endswith("/**"):
            prefix = pat[:-3].rstrip("/")
            return normalized == prefix or normalized.startswith(prefix + "/")
        if pat.startswith("**/"):
            suffix = pat[3:]
            return normalized.endswith(suffix) or fnmatch(normalized, pat.replace("**", "*"))
        return fnmatch(normalized, pat.replace("**", "*"))

    return fnmatch(normalized, pat)


def is_writable_path(path: str) -> bool:
    """True if path is under data/reports/ or data/exports/ (any depth)."""
    normalized = to_data_relative_path(path)
    if not normalized:
        return False
    parts = PurePosixPath(normalized).parts
    return bool(parts) and parts[0] in WRITABLE_SUBDIRS


def writable_path_denial_reason(path: str) -> str:
    return (
        f"produce mode: cannot write to {path!r}; "
        "use a path under data/reports/ or data/exports/"
    )
