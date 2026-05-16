import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "data"


@dataclass(frozen=True)
class ContextCompactConfig:
    context_limit: int = 50_000
    persist_threshold: int = 30_000
    preview_chars: int = 2_000
    keep_recent_tool_results: int = 3
    micro_compact_min_chars: int = 120
    keep_tail_turns: int = 1
    summary_max_tokens: int = 2_000
    summary_input_chars: int = 80_000
    max_recent_files: int = 5
    transcript_dir: Path = DATA_DIR / ".transcripts"
    tool_results_dir: Path = DATA_DIR / ".task_outputs" / "tool-results"
    enabled: bool = True

    @classmethod
    def from_env(cls) -> "ContextCompactConfig":
        def _int(name: str, default: int) -> int:
            raw = os.environ.get(name)
            if raw is None or raw.strip() == "":
                return default
            return int(raw)

        enabled_raw = os.environ.get("CONTEXT_COMPACT_ENABLED", "true").strip().lower()
        enabled = enabled_raw not in ("0", "false", "no", "off")
        return cls(
            context_limit=_int("CONTEXT_LIMIT", 50_000),
            persist_threshold=_int("PERSIST_THRESHOLD", 30_000),
            preview_chars=_int("PREVIEW_CHARS", 2_000),
            keep_recent_tool_results=_int("KEEP_RECENT_TOOL_RESULTS", 3),
            enabled=enabled,
        )


DEFAULT_CONFIG = ContextCompactConfig.from_env()
