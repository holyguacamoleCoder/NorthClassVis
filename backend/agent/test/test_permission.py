import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from permission import CapabilityMode, PermissionManager, filter_tools
from permission.approval import DenyAskApprovalHandler
from permission.paths import path_matches_pattern
from tools.schemas import TOOLS


def test_path_matches_nested_reports():
    assert path_matches_pattern("reports/s1/out.md", "reports/**")
    assert path_matches_pattern("exports/2024/q1.pdf", "exports/**")
    assert not path_matches_pattern("scratch.txt", "reports/**")


def test_consult_blocks_write():
    pm = PermissionManager(mode=CapabilityMode.CONSULT)
    decision = pm.check("write_file", {"path": "reports/a.md"})
    assert decision["behavior"] == "deny"


def test_consult_allows_read():
    pm = PermissionManager(mode=CapabilityMode.CONSULT)
    decision = pm.check("read_file", {"path": "Data_StudentInfo.csv"})
    assert decision["behavior"] == "allow"


def test_analyze_blocks_write():
    pm = PermissionManager(mode=CapabilityMode.ANALYZE)
    decision = pm.check("write_file", {"path": "reports/a.md"})
    assert decision["behavior"] == "deny"


def test_analyze_allows_todo_write():
    pm = PermissionManager(mode=CapabilityMode.ANALYZE)
    decision = pm.check("todo_write", {"items": []})
    assert decision["behavior"] == "allow"


def test_produce_allows_reports():
    pm = PermissionManager(mode=CapabilityMode.PRODUCE)
    decision = pm.check("write_file", {"path": "reports/s1/out.md", "content": "x"})
    assert decision["behavior"] == "allow"


def test_produce_allows_nested_reports():
    pm = PermissionManager(mode=CapabilityMode.PRODUCE)
    decision = pm.check(
        "write_file", {"path": "reports/session1/chapter/summary.md", "content": "x"}
    )
    assert decision["behavior"] == "allow"


def test_produce_denies_raw_data_csv():
    pm = PermissionManager(mode=CapabilityMode.PRODUCE)
    decision = pm.check("write_file", {"path": "Data_StudentInfo.csv", "content": "x"})
    assert decision["behavior"] == "deny"


def test_produce_allows_absolute_path_under_data():
    pm = PermissionManager(mode=CapabilityMode.PRODUCE)
    data_dir = Path(__file__).resolve().parents[3] / "data"
    abs_path = (data_dir / "reports" / "demo" / "session1" / "summary.md").resolve()
    decision = pm.check("write_file", {"path": str(abs_path), "content": "x"})
    assert decision["behavior"] == "allow"


def test_produce_allows_data_prefix_path():
    pm = PermissionManager(mode=CapabilityMode.PRODUCE)
    decision = pm.check("write_file", {"path": "data/reports/out.md", "content": "x"})
    assert decision["behavior"] == "allow"


def test_produce_denies_outside_reports():
    pm = PermissionManager(mode=CapabilityMode.PRODUCE, approval=DenyAskApprovalHandler())
    decision = pm.check("write_file", {"path": "scratch.txt", "content": "x"})
    assert decision["behavior"] == "deny"
    assert "reports" in decision["reason"]


def test_remember_allow_rule():
    pm = PermissionManager(mode=CapabilityMode.PRODUCE)
    pm.remember_allow("write_file", {"path": "scratch.txt"})
    decision = pm.check("write_file", {"path": "scratch.txt", "content": "x"})
    assert decision["behavior"] == "allow"


def test_filter_tools_excludes_write_in_consult():
    names = {t["function"]["name"] for t in filter_tools(TOOLS, CapabilityMode.CONSULT)}
    assert "write_file" not in names
    assert "edit_file" not in names
    assert "read_file" in names


def test_filter_tools_includes_session_in_analyze():
    names = {t["function"]["name"] for t in filter_tools(TOOLS, CapabilityMode.ANALYZE)}
    assert "todo_write" in names
    assert "compact" in names
    assert "write_file" not in names


def test_filter_tools_includes_write_in_produce():
    names = {t["function"]["name"] for t in filter_tools(TOOLS, CapabilityMode.PRODUCE)}
    assert "write_file" in names


def test_safe_path_error_message():
    from tools.base_tool import WORKSPACE_PATH_ERROR, run_read_file

    out = run_read_file("../backend/agent/loop.py")
    assert out == WORKSPACE_PATH_ERROR


if __name__ == "__main__":
    tests = [
        test_path_matches_nested_reports,
        test_consult_blocks_write,
        test_consult_allows_read,
        test_analyze_blocks_write,
        test_analyze_allows_todo_write,
        test_produce_allows_reports,
        test_produce_allows_nested_reports,
        test_produce_denies_raw_data_csv,
        test_produce_allows_absolute_path_under_data,
        test_produce_allows_data_prefix_path,
        test_produce_denies_outside_reports,
        test_remember_allow_rule,
        test_filter_tools_excludes_write_in_consult,
        test_filter_tools_includes_session_in_analyze,
        test_filter_tools_includes_write_in_produce,
        test_safe_path_error_message,
    ]
    for fn in tests:
        fn()
        print(f"OK {fn.__name__}")
    print(f"ALL {len(tests)} PASSED")
