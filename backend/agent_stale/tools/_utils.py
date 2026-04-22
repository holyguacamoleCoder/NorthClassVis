# 工具层共用工具函数。

from typing import Any, List


def ensure_list(val: Any) -> List[Any]:
    if val is None:
        return []
    return val if isinstance(val, list) else [val]
