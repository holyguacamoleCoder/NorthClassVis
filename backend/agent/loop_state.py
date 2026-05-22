"""Shared loop state dataclass (avoids circular imports between loop and session)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from context.state import CompactState
from hooks import HookManager
from permission import PermissionManager
from recovery import RecoveryState
from skills import SkillRegistry


@dataclass
class AnalysisToolContext:
    """本会话内 query_data → aggregate_data 的衔接状态（内存，不持久化）。

    query_data 返回 TabularResult JSON 后，runtime 调用 note_query_result 更新此处；
    下一轮若模型调用 aggregate_data 却未传 input，tools.runtime.data_chain 会用
    last_result_ref 自动填入 input.result_ref。同批内多次 query 时仍以 batch 内
    最近一次 ref 为准（见 execute_tool_calls 的 batch_query_refs）。
    """

    # 最近一次成功 query 在 result_store 中的引用 id（meta.result_ref）
    last_result_ref: str | None = None
    # 该次查询的逻辑资源，如 submit_record_joined
    last_resource: str | None = None
    # 该次扫描行数，供日志或后续提示使用
    last_rows_scanned: int | None = None

    def note_query_result(self, payload: dict) -> None:
        """从 query_data 的 TabularResult dict 提取 meta，更新本会话最近一次查询摘要。"""
        meta = payload.get("meta") or {}
        ref = meta.get("result_ref")
        if ref:
            self.last_result_ref = str(ref)
        self.last_resource = payload.get("resource") or meta.get("resource")
        scanned = meta.get("rows_scanned")
        if scanned is not None:
            try:
                self.last_rows_scanned = int(scanned)
            except (TypeError, ValueError):
                pass


@dataclass
class LoopState:
    messages: List[Dict[str, Any]]
    compact: CompactState = field(default_factory=CompactState)
    permission: PermissionManager | None = None
    hooks: HookManager | None = None
    session_context: list[str] = field(default_factory=list)
    skills: SkillRegistry | None = None
    session_id: str | None = None
    messages_count: int = 1
    turn_count: int = 1
    continue_reason: str | None = None
    recovery: RecoveryState = field(default_factory=RecoveryState)
    # 跨轮保留：传给 execute_tool_calls，供 data_chain 自动衔接 aggregate input
    analysis_context: AnalysisToolContext = field(default_factory=AnalysisToolContext)
