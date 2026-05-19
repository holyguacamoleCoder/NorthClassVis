import random
import time
from typing import Callable

from .config import RecoveryConfig


def backoff_delay(attempt: int, *, config: RecoveryConfig) -> float:
    """Exponential backoff with jitter: base * 2^attempt + uniform(0, 1)."""
    delay = min(config.backoff_base_delay * (2**attempt), config.backoff_max_delay)
    return delay + random.uniform(0, 1)


def sleep_backoff(
    attempt: int,
    *,
    config: RecoveryConfig,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> float:
    delay = backoff_delay(attempt, config=config)
    sleep_fn(delay)
    return delay
