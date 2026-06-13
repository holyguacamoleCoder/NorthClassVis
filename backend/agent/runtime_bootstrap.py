"""Import path setup for CLI / direct script runs (backend + backend/agent on sys.path)."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

_AGENT_ROOT = Path(__file__).resolve().parent
_BACKEND_ROOT = _AGENT_ROOT.parent
_bootstrapped = False


def _pin_stdlib_http() -> None:
    """Load stdlib ``http.client`` before ``backend/agent/http`` shadows ``http`` on sys.path."""
    if "http.client" in sys.modules:
        return
    agent_s = str(_AGENT_ROOT)
    saved_path = sys.path[:]
    try:
        sys.path[:] = [p for p in sys.path if p != agent_s]
        importlib.import_module("http.client")
        if "http.cookiejar" not in sys.modules:
            importlib.import_module("http.cookiejar")
    finally:
        sys.path[:] = saved_path


def bootstrap_runtime_paths() -> None:
    global _bootstrapped
    if _bootstrapped:
        return
    _pin_stdlib_http()
    agent_s = str(_AGENT_ROOT)
    backend_s = str(_BACKEND_ROOT)
    # Re-order: script dir often pre-inserts agent; adding backend at 0 alone
    # makes backend/tools shadow agent/tools.
    for entry in (agent_s, backend_s):
        while entry in sys.path:
            sys.path.remove(entry)
    sys.path.insert(0, backend_s)
    sys.path.insert(0, agent_s)
    _bootstrapped = True


bootstrap_runtime_paths()
