# 工具基类：入口 call() 调子类 perform()，统一计时与 ToolResult 拼装。

import time


def param_schema(properties=None, required=None):
    """JSON Schema for tool parameters."""
    return {"type": "object", "properties": properties or {}, "additionalProperties": False, "required": required or []}


def make_tool_result(
    tool,
    input_params,
    status="ok",
    summary="",
    raw=None,
    evidence=None,
    visual_hints=None,
    duration_ms=0,
    error=None,
    round_=None,
    parallel_group=None,
    coverage=None,
    quality=None,
):
    """拼装标准 ToolResult 字典，供 BaseTool.call 与 runner 边界情况使用。"""
    result = {
        "tool": tool,
        "input": dict(input_params or {}),
        "status": status,
        "summary": summary or "",
        "raw": raw,
        "evidence": evidence or [],
        "visual_hints": visual_hints or [],
        "duration_ms": duration_ms,
        "error": error,
    }
    if round_ is not None:
        result["round"] = round_
    if parallel_group is not None:
        result["parallel_group"] = parallel_group
    if coverage is not None:
        result["coverage"] = coverage
    if quality is not None:
        result["quality"] = quality
    return result


class BaseTool:
    """工具基类：子类实现 perform()；对外入口为 call()。"""

    name = ""
    description = ""
    parameters = None  # JSON Schema dict
    tier = "L1"
    parallel_safe = True
    needs_feature_factory = False

    def get_spec(self):
        """返回 OpenAI function 格式：name, description, parameters。"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters or param_schema(),
        }

    def perform(self, params, config, feature_factory=None):
        """
        子类实现：执行工具逻辑。params 为调用方传入，子类内做参数归一化。
        返回 (summary, step_dict)。step_dict 需含 tool, params, summary；可选 raw, evidence, visual_hints, coverage, quality。
        """
        raise NotImplementedError

    def get_visual_hints(self, step_dict):
        """子类可覆盖：当 step_dict 未带 visual_hints 时，按工具语义补全。默认返回 []。"""
        return []

    def call(self, params, config, feature_factory=None, round_=None, parallel_group=None):
        """
        对外入口：计时、调用 perform()、拼装 ToolResult，异常时返回同结构 error 形态。
        """
        start = time.perf_counter()
        input_params = dict(params or {})
        try:
            if self.needs_feature_factory and not feature_factory:
                duration_ms = int((time.perf_counter() - start) * 1000)
                return make_tool_result(
                    tool=self.name,
                    input_params=input_params,
                    status="error",
                    summary="需要特征工厂",
                    duration_ms=duration_ms,
                    round_=round_,
                    parallel_group=parallel_group,
                )
            summary, step_dict = self.perform(params, config, feature_factory if self.needs_feature_factory else None)
            step_dict = step_dict or {}
            duration_ms = int((time.perf_counter() - start) * 1000)
            evidence = list(step_dict.get("evidence") or [])
            if not evidence and summary:
                evidence = [{"tool": self.name, "summary": summary}]
            for e in evidence:
                if isinstance(e, dict):
                    e["tool"] = self.name
            visual_hints = list(step_dict.get("visual_hints") or [])
            if not visual_hints:
                visual_hints = self.get_visual_hints(step_dict)
            return make_tool_result(
                tool=self.name,
                input_params=step_dict.get("params") or input_params,
                status="ok",
                summary=summary or step_dict.get("summary") or "",
                raw=step_dict.get("raw"),
                evidence=evidence,
                visual_hints=visual_hints,
                duration_ms=duration_ms,
                round_=round_,
                parallel_group=parallel_group,
                coverage=step_dict.get("coverage"),
                quality=step_dict.get("quality"),
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return make_tool_result(
                tool=self.name,
                input_params=input_params,
                status="error",
                summary=str(e),
                duration_ms=duration_ms,
                error=str(e),
                round_=round_,
                parallel_group=parallel_group,
            )
