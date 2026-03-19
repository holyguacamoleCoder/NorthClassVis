from typing import List

from agent.common.contracts import ToolResult
from agent.execution.schemas import TaskExecutionRecord
from agent.output.schemas import ResultSummary


def summarize_execution(
    execution_records: List[TaskExecutionRecord],
    tool_results: List[ToolResult],
) -> ResultSummary:
    """根据执行记录与规范化结果生成汇总摘要，用于回答生成与响应装配。"""
    if not execution_records or not tool_results:
        return ResultSummary(overall_status="empty")

    completed_ids = []
    failed_ids = []
    partial_ids = []
    key_findings = []
    unresolved = []
    evidence = []
    visual_links = []

    for rec, tr in zip(execution_records, tool_results):
        status = (rec.status or "").lower()
        if status == "ok":
            completed_ids.append(rec.task_id)
        elif status in ("fail", "error"):
            failed_ids.append(rec.task_id)
        else:
            partial_ids.append(rec.task_id)

        if tr.summary:
            key_findings.append(str(tr.summary))
        if tr.error:
            unresolved.append(str(tr.error))

        for e in tr.evidence or []:
            if isinstance(e, dict) and e.get("tool") is not None:
                evidence.append({"tool": e.get("tool"), "summary": e.get("summary", "")})
        for h in tr.visual_hints or []:
            if isinstance(h, dict) and h.get("view"):
                visual_links.append({"view": h.get("view"), "params": h.get("params") or {}})

    if failed_ids:
        overall = "partial" if completed_ids else "failed"
    else:
        overall = "complete"

    return ResultSummary(
        overall_status=overall,
        completed_task_ids=completed_ids,
        failed_task_ids=failed_ids,
        partial_task_ids=partial_ids,
        key_findings=key_findings,
        unresolved_points=unresolved,
        evidence=evidence,
        visual_links=visual_links,
    )

