import os
from dataclasses import dataclass

from common.prompts import OUTPUT_CONTINUATION_MESSAGE


@dataclass(frozen=True)
class RecoveryConfig:
    enabled: bool = True
    max_attempts: int = 3
    backoff_base_delay: float = 1.0
    backoff_max_delay: float = 30.0
    continuation_message: str = OUTPUT_CONTINUATION_MESSAGE

    @classmethod
    def from_env(cls) -> "RecoveryConfig":
        def _int(name: str, default: int) -> int:
            raw = os.environ.get(name)
            if raw is None or raw.strip() == "":
                return default
            return int(raw)

        def _float(name: str, default: float) -> float:
            raw = os.environ.get(name)
            if raw is None or raw.strip() == "":
                return default
            return float(raw)

        enabled_raw = os.environ.get("RECOVERY_ENABLED", "true").strip().lower()
        enabled = enabled_raw not in ("0", "false", "no", "off")
        return cls(
            enabled=enabled,
            max_attempts=_int("RECOVERY_MAX_ATTEMPTS", 3),
            backoff_base_delay=_float("RECOVERY_BACKOFF_BASE", 1.0),
            backoff_max_delay=_float("RECOVERY_BACKOFF_MAX", 30.0),
        )


DEFAULT_RECOVERY_CONFIG = RecoveryConfig.from_env()
