# 执行结果规范化：runner 原始结果 -> ToolResult；并按 PlanStep.verification_rule 做结果校验。

from typing import List

from agent.common.contracts import PlanStep
from agent.common.contracts import ToolResult
from agent.common.log_config import ensure_agent_logger

_agent_logger = ensure_agent_logger()


def _evaluate_verification_rule(rule: str, result: ToolResult) -> bool:
    """
    对单条 verification_rule 做安全、有限的解释，返回是否通过。
    仅支持字面规则，避免 eval；未识别规则视为通过。
    """
    if not (rule or "").strip():
        return True
    r = (rule or "").strip()
    data = result.raw if result.raw is not None else (result.summary or "")
    if r == "data is not None":
        return data is not None
    if r == "status==ok":
        return (result.status or "").lower() == "ok"
    if r.startswith("data is not None") or r == "data":
        return data is not None
    _agent_logger.debug("Execution verification_rule 未识别，视为通过: %s", r[:80])
    return True


def verify_tool_results(plan_steps: List[PlanStep], tool_results: List[ToolResult]) -> List[ToolResult]:
    """
    按 plan_steps 中每条 step 的 verification_rule 校验对应 ToolResult；
    不通过则返回新 ToolResult（status=fail, error 注明校验失败），通过则原样返回。
    """
    if not plan_steps or not tool_results or len(plan_steps) != len(tool_results):
        return tool_results
    out = []
    for i, step in enumerate(plan_steps):
        res = tool_results[i]
        rule = getattr(step, "verification_rule", None) or ""
        if not rule:
            out.append(res)
            continue
        if _evaluate_verification_rule(rule, res):
            out.append(res)
            continue
        _agent_logger.info("Execution verify_tool_results: step %d 校验未通过 rule=%s", i, rule[:60])
        out.append(
            ToolResult(
                tool=res.tool,
                params=res.params,
                status="fail",
                summary=res.summary,
                evidence=res.evidence,
                visual_hints=res.visual_hints,
                raw=res.raw,
                duration_ms=res.duration_ms,
                coverage=res.coverage,
                quality=res.quality,
                error=(res.error or "").strip() + "; verification_rule failed: " + rule[:100],
            )
        )
    return out


def extract_tool_results(tool_results) -> List[ToolResult]:
    """将 runner 返回的 tool 结果 dict 列表规范为 ToolResult 列表。"""
    raw = tool_results or []
    out = []
    for tr in raw:
        out.append(
            ToolResult(
                tool=tr.get("tool") or "",
                params=dict(tr.get("input") or {}),
                status=tr.get("status") or "ok",
                summary=tr.get("summary") or "",
                evidence=list(tr.get("evidence") or []),
                visual_hints=list(tr.get("visual_hints") or []),
                raw=tr.get("raw"),
                duration_ms=int(tr.get("duration_ms") or 0),
                coverage=dict(tr.get("coverage") or {}),
                quality=dict(tr.get("quality") or {}),
                error=tr.get("error") or "",
            )
        )
    _agent_logger.debug("Execution extract_tool_results: 输入 %d 条，输出 %d 条 ToolResult", len(raw), len(out))
    return out
