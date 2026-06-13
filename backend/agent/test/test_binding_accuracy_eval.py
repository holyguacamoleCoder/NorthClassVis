"""Smoke test for binding accuracy eval script."""

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "backend" / "agent" / "eval" / "binding_accuracy.py"
JSON_OUT = REPO_ROOT / "data" / "eval" / "binding_accuracy.json"

pytestmark = __import__("pytest").mark.skipif(
    importlib.util.find_spec("numpy") is None,
    reason="numpy 未安装",
)


def test_binding_accuracy_script_runs():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert JSON_OUT.is_file()
    data = __import__("json").loads(JSON_OUT.read_text(encoding="utf-8"))
    assert data["total"] >= 15
    assert data["accuracy_pct"] == 100.0
