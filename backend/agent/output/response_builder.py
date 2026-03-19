import json


def build_response(agent_run, context=None):
    """
    将 agent_run 转为前端契约。
    agent_run 含：success, answer, actions, tool_results, round_reasons 等
    返回：answer, evidence, actions, visual_links, trace
    """
    tool_results = agent_run.get("tool_results") or []
    answer = agent_run.get("answer") or "当前数据不足以支持该结论。"
    actions = agent_run.get("actions")
    if not isinstance(actions, list):
        actions = [actions] if actions else []

    evidence = []
    for r in tool_results:
        for e in r.get("evidence") or []:
            if isinstance(e, dict) and e.get("tool") is not None:
                evidence.append({"tool": e["tool"], "summary": e.get("summary", "")})
        if not (r.get("evidence")):
            evidence.append({"tool": r.get("tool", ""), "summary": r.get("summary", "")})

    visual_links = []
    seen = set()
    for r in tool_results:
        for h in r.get("visual_hints") or []:
            if not isinstance(h, dict) or not h.get("view"):
                continue
            key = (h.get("view"), json.dumps(h.get("params") or {}, sort_keys=True))
            if key not in seen:
                seen.add(key)
                visual_links.append({"view": h["view"], "params": h.get("params") or {}})

    reason_by_round = {}
    for rr in agent_run.get("round_reasons") or []:
        if isinstance(rr, dict) and rr.get("round") is not None and rr.get("reason"):
            reason_by_round[rr["round"]] = rr["reason"]

    steps = []
    for r in tool_results:
        step = {
            "tool": r.get("tool", ""),
            "params": r.get("input"),
            "summary": r.get("summary", ""),
        }
        if r.get("round") is not None:
            step["round"] = r["round"]
        if r.get("parallel_group") is not None:
            step["parallel_group"] = r["parallel_group"]
        if r.get("status"):
            step["status"] = r["status"]
        if r.get("duration_ms") is not None:
            step["duration_ms"] = r["duration_ms"]
        if r.get("coverage") is not None:
            step["coverage"] = r.get("coverage")
        if r.get("quality") is not None:
            step["quality"] = r.get("quality")
        if r.get("error"):
            step["error"] = r.get("error")
        if step.get("round") is not None and reason_by_round.get(step["round"]):
            step["reason"] = reason_by_round[step["round"]]
        steps.append(step)
    trace = {"steps": steps}
    if reason_by_round and not steps:
        trace["reasons"] = [{"round": k, "reason": v} for k, v in sorted(reason_by_round.items())]

    resp = {
        "answer": answer,
        "evidence": evidence,
        "actions": actions,
        "visual_links": visual_links,
        "trace": trace,
    }

    goal_check = agent_run.get("goal_check")
    if goal_check:
        resp["goal_check"] = goal_check
    summary = agent_run.get("summary")
    if summary:
        resp["summary"] = summary
    return resp
