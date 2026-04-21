# 保证从 backend 或项目根运行 pytest 时都能正确解析 agent 包。
# 注册按模块筛选的 marker：-m plan / -m execution / -m intent / -m integration / -m llm
import os
import sys

import pytest

_backend = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _backend not in sys.path:
    sys.path.insert(0, _backend)

# 若项目存在 backend/.env，则一并加载；当前 llm 测试默认用 fake client，不依赖外网。
_env_path = os.path.join(_backend, ".env")
try:
    from dotenv import load_dotenv
    load_dotenv(_env_path)
except ImportError:
    pass
except Exception:
    pass


def pytest_configure(config):
    config.addinivalue_line("markers", "plan: 规划模块单测（agent/test/plan/）")
    config.addinivalue_line("markers", "execution: 执行编译模块单测（agent/test/execution/）")
    config.addinivalue_line("markers", "intent: 意图模块单测（agent/test/intent/）")
    config.addinivalue_line("markers", "integration: 模块集成测试（agent/test/integration/）")
    config.addinivalue_line("markers", "llm: 覆盖 LLM 分支代码路径（默认使用 fake LLM client，不依赖外网）")


def pytest_collection_modifyitems(config, items):
    """按路径自动打 marker，便于 -m execution / -m plan / -m intent / -m integration 单独跑某模块。"""
    for item in items:
        try:
            path = str(item.fspath)
        except Exception:
            path = item.nodeid.replace("\\", os.path.sep)
        norm = path.replace("\\", "/")
        if "/test/execution/" in norm or norm.endswith("/test/execution"):
            item.add_marker(pytest.mark.execution)
        elif "/test/plan/" in norm or norm.endswith("/test/plan"):
            item.add_marker(pytest.mark.plan)
        elif "/test/intent/" in norm or norm.endswith("/test/intent"):
            item.add_marker(pytest.mark.intent)
        elif "/test/integration/" in norm or norm.endswith("/test/integration"):
            item.add_marker(pytest.mark.integration)
