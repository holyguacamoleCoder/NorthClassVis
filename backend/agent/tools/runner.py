# 工具运行器：按名取 Tool、调用 tool.call()，做并行/顺序编排，返回 ToolResult 列表。

import json as _json
from concurrent.futures import ThreadPoolExecutor, as_completed

from agent.tools.base import make_tool_result
from agent.tools.registry import get_tool
from agent.tools.registry import is_parallel_safe


def _run_single(tool_name, args, config, feature_factory, round_=None, parallel_group=None):
    tool = get_tool(tool_name)
    if not tool:
        return make_tool_result(
            tool=tool_name,
            input_params=dict(args or {}),
            status="error",
            summary="未知工具",
            error="未知工具",
            round_=round_,
            parallel_group=parallel_group,
        )
    return tool.call(
        args or {},
        config,
        feature_factory,
        round_=round_,
        parallel_group=parallel_group,
    )


class ToolRunner:
    """持有 config、feature_factory，执行工具调用（ReAct 或 compiler 步骤）。"""

    def __init__(self, config, feature_factory=None):
        self.config = config
        self.feature_factory = feature_factory

    def run_tool_calls(self, tool_calls, round_=0):
        if not tool_calls:
            return []
        invokes = []
        for tc in tool_calls:
            name = tc.get("name") or tc.get("tool") or (tc.get("function") or {}).get("name")
            if not name:
                continue
            args = tc.get("arguments") or tc.get("params") or {}
            if isinstance(args, str):
                try:
                    args = _json.loads(args)
                except Exception:
                    args = {}
            invokes.append((name, dict(args or {})))
        if not invokes:
            return []
        all_safe = all(is_parallel_safe(name) for name, _ in invokes)
        results = [None] * len(invokes)
        if all_safe and len(invokes) > 1:
            with ThreadPoolExecutor(max_workers=min(len(invokes), 8)) as ex:
                futures = {
                    ex.submit(_run_single, name, args, self.config, self.feature_factory, round_, i): i
                    for i, (name, args) in enumerate(invokes)
                }
                for fut in as_completed(futures):
                    idx = futures[fut]
                    try:
                        results[idx] = fut.result()
                    except Exception as e:
                        name, args = invokes[idx]
                        results[idx] = make_tool_result(
                            tool=name,
                            input_params=args,
                            status="error",
                            summary=str(e),
                            error=str(e),
                            round_=round_,
                            parallel_group=idx,
                        )
        else:
            for i, (name, args) in enumerate(invokes):
                results[i] = _run_single(name, args, self.config, self.feature_factory, round_, i)
        return results

    def run_plan_steps(self, plan_steps):
        """执行规划步骤（step.tool 为工具名），返回 ToolResult 列表。"""
        out = []
        for idx, step in enumerate(plan_steps or []):
            tool_name = step.get("tool")
            params = dict(step.get("params") or {})
            tool = get_tool(tool_name)
            if not tool:
                res = make_tool_result(
                    tool=tool_name,
                    input_params=params,
                    status="error",
                    summary="未知工具",
                    error="未知工具",
                    round_=idx,
                )
            else:
                res = tool.call(params, self.config, self.feature_factory, round_=idx, parallel_group=None)
            res["reason"] = step.get("reason") or ""
            res["coverage"] = res.get("coverage") or {}
            res["quality"] = res.get("quality") or {}
            out.append(res)
        return out


def run_tool_calls(tool_calls, config, feature_factory=None, round_=0):
    return ToolRunner(config, feature_factory).run_tool_calls(tool_calls, round_=round_)


def run_plan_steps(plan_steps, config, feature_factory=None):
    return ToolRunner(config, feature_factory).run_plan_steps(plan_steps)
