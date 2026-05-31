import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts" / "hooks"
AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from hooks import HookManager


def _run_hook(
    script: str,
    event: str,
    tool: str,
    inp: dict | None = None,
    extra_env: dict | None = None,
):
    env = os.environ.copy()
    env["HOOK_EVENT"] = event
    env["HOOK_TOOL_NAME"] = tool
    env["HOOK_TOOL_INPUT"] = json.dumps(inp or {})
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_session_start_emits_catalog_json():
    proc = _run_hook("session_start.py", "SessionStart", "")
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert "additionalContext" in out
    ctx = out["additionalContext"]
    assert "Data_StudentInfo" in ctx
    assert "Data_SubmitRecord" in ctx
    assert "resource_registry" in ctx
    assert "student_info" in ctx
    assert "report-delivery" in ctx
    assert "analysis-class" in ctx


def test_audit_read_logs_and_hints_without_limit(tmp_path):
    log = tmp_path / "read.jsonl"
    proc = _run_hook(
        "audit_read.py",
        "PreToolUse",
        "read_file",
        {"path": "Data_StudentInfo.csv"},
        extra_env={"AGENT_READ_AUDIT_LOG": str(log)},
    )
    assert proc.returncode == 2
    assert "limit" in proc.stderr.lower()
    row = json.loads(log.read_text(encoding="utf-8").strip().splitlines()[0])
    assert row["path"] == "Data_StudentInfo.csv"
    assert row["sensitive"] is True


def test_audit_read_no_hint_when_limit_set(tmp_path):
    log = tmp_path / "read.jsonl"
    proc = _run_hook(
        "audit_read.py",
        "PreToolUse",
        "read_file",
        {"path": "Data_StudentInfo.csv", "limit": 20},
        extra_env={"AGENT_READ_AUDIT_LOG": str(log)},
    )
    assert proc.returncode == 0
    assert proc.stderr.strip() == ""


def test_export_manifest_appends(tmp_path):
    manifest = tmp_path / "manifest.jsonl"
    proc = _run_hook(
        "export_manifest.py",
        "PostToolUse",
        "write_file",
        {"path": "exports/out.txt", "content": "hello"},
        extra_env={"AGENT_EXPORT_MANIFEST": str(manifest)},
    )
    assert proc.returncode == 0
    row = json.loads(manifest.read_text(encoding="utf-8").strip())
    assert row["path"] == "exports/out.txt"
    assert row["bytes"] == 5


def test_permission_deny_hint_consult_write():
    proc = _run_hook(
        "permission_deny_hint.py",
        "PermissionDeny",
        "write_file",
        {"path": "reports/academic_analysis_Class1.md", "content": "# x"},
        extra_env={
            "HOOK_PERMISSION_MODE": "consult",
            "HOOK_DENY_REASON": "consult: write operations are blocked",
            "HOOK_DENY_TYPE": "policy",
        },
    )
    assert proc.returncode == 2
    assert "produce" in proc.stderr.lower()
    assert "consult" in proc.stderr.lower()


def test_permission_deny_hint_skips_read_tools():
    proc = _run_hook(
        "permission_deny_hint.py",
        "PermissionDeny",
        "read_file",
        {"path": "Data_StudentInfo.csv"},
        extra_env={
            "HOOK_PERMISSION_MODE": "consult",
            "HOOK_DENY_REASON": "consult: tool read_file not allowed",
            "HOOK_DENY_TYPE": "policy",
        },
    )
    assert proc.returncode == 0
    assert proc.stderr.strip() == ""


def test_hooks_json_loads_project_defaults():
    cfg = ROOT / ".hooks.json"
    assert cfg.is_file()
    hm = HookManager(config_path=cfg, workdir=ROOT)
    assert len(hm.hooks["SessionStart"]) == 1
    assert len(hm.hooks["PreToolUse"]) == 1
    assert len(hm.hooks["PermissionDeny"]) == 2


def test_session_start_via_hook_manager(tmp_path):
    cfg = tmp_path / ".hooks.json"
    cfg.write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [
                        {"command": f'"{sys.executable}" scripts/hooks/session_start.py'}
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    hm = HookManager(config_path=cfg, workdir=ROOT)
    result = hm.run_hooks("SessionStart", {"tool_name": "", "tool_input": {}})
    assert result.messages
    assert "Data catalog" in result.messages[0] or "Data_StudentInfo" in result.messages[0]
