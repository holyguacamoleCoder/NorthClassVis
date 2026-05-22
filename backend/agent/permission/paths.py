"""Path policy for permission rules (sandbox: tools.handlers.base_tool._safe_path)."""

from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

from common.paths import DATA_DIR, DATA_GOVERNANCE_DENY_PATTERNS, strip_data_prefix

WRITABLE_SUBDIRS = ("reports", "exports")

# Used by rules.py and path policy checks (supports ** for nested paths).
WRITE_ALLOW_PATTERNS = tuple(f"{name}/**" for name in WRITABLE_SUBDIRS)
WRITE_DENY_PATTERNS = ("Data_*.csv",)


def normalize_path(path: str | None) -> str:
    return strip_data_prefix(path or "")


def resolve_data_relative_path(path: str | None) -> str:
    """
  Resolve a tool path to a stable location relative to data/.

  Rejects paths outside the data workspace (including backend/.agent) and
  normalizes ``..`` so ``reports/../.sessions`` cannot bypass policy.
    """
    raw = str(path or "").strip()
    if not raw:
        return ""

    candidate = Path(raw)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (DATA_DIR / normalize_path(raw)).resolve()

    try:
        rel = resolved.relative_to(DATA_DIR.resolve())
    except ValueError as exc:
        raise ValueError("path outside data workspace") from exc

    return rel.as_posix()


def to_data_relative_path(path: str | None) -> str:
    """
    Normalize tool path for permission checks: relative to data/, forward slashes.
    Falls back to non-resolving normalize only when resolution is impossible.
    """
    raw = str(path or "").strip()
    if not raw:
        return ""
    try:
        return resolve_data_relative_path(raw)
    except ValueError:
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


def is_raw_dataset_path(path: str) -> bool:
    """True for canonical raw CSV datasets (use inspect_schema / query_data instead of read_file)."""
    normalized = to_data_relative_path(path)
    if not normalized:
        return False
    if path_matches_pattern(normalized, "Data_StudentInfo.csv"):
        return True
    if path_matches_pattern(normalized, "Data_TitleInfo.csv"):
        return True
    if normalized.startswith("Data_SubmitRecord/"):
        return True
    return False


def raw_dataset_read_denial_reason(mode: str) -> str:
    if mode == "consult":
        return (
            "原始学业 CSV 请用 inspect_schema（resource id 见 data/meta/resource_registry.yaml），"
            "勿 read_file。统计与筛选请切换到 analyze 模式后使用 query_data / aggregate_data。"
        )
    return (
        "原始学业 CSV 请用 query_data / aggregate_data（resource id 见 resource_registry），"
        "勿 read_file。可先 inspect_schema 查看字段。"
    )


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


def is_governance_data_path(path: str) -> bool:
    """True for legacy agent runtime dirs that must not live under data/."""
    try:
        normalized = resolve_data_relative_path(path)
    except ValueError:
        # Absolute paths to backend/.agent etc. are outside data/.
        return True
    if not normalized:
        return False
    parts = PurePosixPath(normalized).parts
    if any(part.startswith(".") or part == ".agent" for part in parts):
        return True
    return any(path_matches_pattern(normalized, pat) for pat in DATA_GOVERNANCE_DENY_PATTERNS)


def governance_path_denial_reason(path: str) -> str:
    return (
        f"Path {path!r} is agent runtime state, not part of the data plane. "
        "Use reports/ or exports/ under data/ for deliverables."
    )
