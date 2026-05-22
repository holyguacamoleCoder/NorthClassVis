import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from hooks import HookManager
from hooks.manager import HOOK_EVENTS
from permission import CapabilityMode, PermissionManager
from tools.runtime.executor import execute_tool_calls


def test_hook_manager_empty_when_no_config(tmp_path):
    hm = HookManager(config_path=tmp_path / "missing.json")
    result = hm.run_hooks("PreToolUse", {"tool_name": "bash", "tool_input": {}})
    assert not result.blocked
    assert result.messages == []


def test_hook_manager_loads_config(tmp_path):
    config = {
        "hooks": {
            "PreToolUse": [{"matcher": "read_file", "command": "echo ok"}],
        }
    }
    cfg = tmp_path / ".hooks.json"
    cfg.write_text(json.dumps(config), encoding="utf-8")
    hm = HookManager(config_path=cfg, workdir=tmp_path)
    assert len(hm.hooks["PreToolUse"]) == 1


def test_matcher_skips_non_matching_tool(tmp_path):
    cfg = tmp_path / ".hooks.json"
    cfg.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [{"matcher": "bash", "command": "exit 1"}],
                }
            }
        ),
        encoding="utf-8",
    )
    hm = HookManager(config_path=cfg, workdir=tmp_path)
    with patch("hooks.manager.subprocess.run") as run:
        result = hm.run_hooks(
            "PreToolUse",
            {"tool_name": "read_file", "tool_input": {"path": "a.txt"}},
        )
    run.assert_not_called()
    assert not result.blocked


def test_exit_code_1_blocks(tmp_path):
    cfg = tmp_path / ".hooks.json"
    cfg.write_text(
        json.dumps({"hooks": {"PreToolUse": [{"command": "exit 1"}]}}),
        encoding="utf-8",
    )
    hm = HookManager(config_path=cfg, workdir=tmp_path)
    mock_proc = MagicMock(returncode=1, stdout="", stderr="nope")
    with patch("hooks.manager.subprocess.run", return_value=mock_proc):
        result = hm.run_hooks("PreToolUse", {"tool_name": "bash", "tool_input": {}})
    assert result.blocked
    assert result.block_reason == "nope"


def test_exit_code_2_injects_message(tmp_path):
    cfg = tmp_path / ".hooks.json"
    cfg.write_text(
        json.dumps({"hooks": {"PreToolUse": [{"command": "exit 2"}]}}),
        encoding="utf-8",
    )
    hm = HookManager(config_path=cfg, workdir=tmp_path)
    mock_proc = MagicMock(returncode=2, stdout="", stderr="inject me")
    with patch("hooks.manager.subprocess.run", return_value=mock_proc):
        result = hm.run_hooks("PreToolUse", {"tool_name": "bash", "tool_input": {}})
    assert not result.blocked
    assert result.messages == ["inject me"]


def test_updated_input_from_json_stdout(tmp_path):
    cfg = tmp_path / ".hooks.json"
    cfg.write_text(
        json.dumps({"hooks": {"PreToolUse": [{"command": "echo json"}]}}),
        encoding="utf-8",
    )
    hm = HookManager(config_path=cfg, workdir=tmp_path)
    stdout = json.dumps({"updatedInput": {"path": "reports/x.md"}})
    mock_proc = MagicMock(returncode=0, stdout=stdout, stderr="")
    ctx = {"tool_name": "read_file", "tool_input": {"path": "old.md"}}
    with patch("hooks.manager.subprocess.run", return_value=mock_proc):
        hm.run_hooks("PreToolUse", ctx)
    assert ctx["tool_input"]["path"] == "reports/x.md"


def test_require_trust_skips_hooks(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_HOOKS_REQUIRE_TRUST", "1")
    cfg = tmp_path / ".hooks.json"
    cfg.write_text(
        json.dumps({"hooks": {"PreToolUse": [{"command": "exit 1"}]}}),
        encoding="utf-8",
    )
    hm = HookManager(config_path=cfg, workdir=tmp_path, require_trust=None)
    with patch("hooks.manager.subprocess.run") as run:
        result = hm.run_hooks("PreToolUse", {"tool_name": "bash", "tool_input": {}})
    run.assert_not_called()
    assert not result.blocked


def test_permission_deny_injects_message(tmp_path):
    cfg = tmp_path / ".hooks.json"
    cfg.write_text(
        json.dumps({"hooks": {"PermissionDeny": [{"command": "exit 2"}]}}),
        encoding="utf-8",
    )
    hm = HookManager(config_path=cfg, workdir=tmp_path)
    mock_proc = MagicMock(returncode=2, stdout="", stderr="switch to produce")
    with patch("hooks.manager.subprocess.run", return_value=mock_proc):
        result = hm.run_hooks(
            "PermissionDeny",
            {
                "tool_name": "write_file",
                "tool_input": {"path": "reports/x.md"},
                "deny_reason": "consult: write operations are blocked",
                "permission_mode": "consult",
                "deny_type": "policy",
            },
        )
    assert not result.blocked
    assert result.messages == ["switch to produce"]


def test_executor_permission_deny_runs_hook():
    hm = HookManager(config_path=Path("/nonexistent/hooks.json"))
    hm.hooks = {event: [] for event in HOOK_EVENTS}
    hm.hooks["PermissionDeny"] = [{"matcher": "write_file", "command": "deny-hint"}]

    mock_proc = MagicMock(returncode=2, stdout="", stderr="use produce mode")
    permission = PermissionManager(mode=CapabilityMode.CONSULT)

    with patch("hooks.manager.subprocess.run", return_value=mock_proc):
        results = execute_tool_calls(
            [
                {
                    "id": "c1",
                    "name": "write_file",
                    "arguments": {"path": "reports/a.md", "content": "hi"},
                }
            ],
            permission=permission,
            hooks=hm,
        )

    assert len(results) == 1
    assert "Permission denied" in results[0]["content"]
    assert "use produce mode" in results[0]["content"]
    assert "[Hook message]" in results[0]["content"]


def test_executor_pre_hook_blocks_before_permission():
    hm = HookManager(config_path=Path("/nonexistent/hooks.json"))
    hm.hooks = {
        event: [] for event in HOOK_EVENTS
    }
    hm.hooks["PreToolUse"] = [{"command": "block"}]

    mock_proc = MagicMock(returncode=1, stdout="", stderr="blocked by policy")
    with patch("hooks.manager.subprocess.run", return_value=mock_proc):
        results = execute_tool_calls(
            [{"id": "c1", "name": "read_file", "arguments": {"path": "a.csv"}}],
            hooks=hm,
        )
    assert len(results) == 1
    assert "PreToolUse hook" in results[0]["content"]
    assert "blocked by policy" in results[0]["content"]
