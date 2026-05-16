from typing import Any

# 后续变为tiktoken等
def estimate_context_size(messages: list[dict[str, Any]]) -> int:
    return len(str(messages))
