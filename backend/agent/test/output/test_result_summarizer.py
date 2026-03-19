from agent.common.contracts import ToolResult
from agent.execution.schemas import TaskExecutionRecord
from agent.output.result_summarizer import summarize_execution


def test_summarize_execution_classifies_status_and_collects_findings():
    rec_ok = TaskExecutionRecord(task_id="ok", tool="query_class", params={}, status="ok")
    rec_fail = TaskExecutionRecord(task_id="fail", tool="query_student", params={}, status="fail")

    tr_ok = ToolResult(tool="query_class", params={}, status="ok", summary="class trend", coverage={"covered": True})
    tr_fail = ToolResult(tool="query_student", params={}, status="fail", summary="", error="boom")

    summary = summarize_execution([rec_ok, rec_fail], [tr_ok, tr_fail])

    assert summary.overall_status in ("partial", "failed")
    assert "ok" in summary.completed_task_ids
    assert "fail" in summary.failed_task_ids
    assert "class trend" in summary.key_findings
    assert any("boom" in msg for msg in summary.unresolved_points)

