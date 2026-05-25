"""Shared loop state dataclass (avoids circular imports between loop and session)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, TYPE_CHECKING

from context.state import CompactState
from hooks import HookManager
from permission import PermissionManager
from recovery import RecoveryState
from skills import SkillRegistry


if TYPE_CHECKING:
    from data.filter_context import FilterContext


@dataclass(frozen=True)
class QuerySnapshot:
    """一次 query_data 在内存工作集中的摘要。"""

    result_ref: str
    result_rows: int
    query_limit: int | None = None
    rows_scanned: int | None = None
    resource: str | None = None
    dataset_id: str | None = None


@dataclass
class AnalysisToolContext:
    """
    查询结果的双层状态（类比内存 + 硬盘）。

    - **硬盘**：``result_ref`` → ``task_outputs/query-results/*.json``（由 result_store 写入）；
      会话目录 ``datasets.jsonl`` 为目录项（见 data.dataset_registry）。
    - **内存（工作集）**：``working_active_ref`` = 当前 *教师一轮提问* 内最后一次 query 的 ref；
      新一轮用户消息时 ``begin_user_turn()`` 清空，避免跨题误用。
    - **同批工具**：``batch`` 内以执行顺序为准；executor 会先跑完本批所有 query_data 再跑 aggregate。
    """

    session_id: str | None = None
    user_turn: int = 0
    current_user_message: str | None = None
    working_active_ref: str | None = None
    last_dataset_id: str | None = None
    turn_snapshots: list[QuerySnapshot] = field(default_factory=list)

    # 兼容旧字段（= working_active_ref，不再跨 turn 做 limit 启发式）
    last_result_ref: str | None = None
    last_resource: str | None = None
    last_rows_scanned: int | None = None
    last_result_rows: int | None = None

    def begin_user_turn(self, user_message: str | None = None) -> None:
        """新用户消息：清空工作集指针（硬盘/catalog 保留）。"""
        self.user_turn += 1
        text = (user_message or "").strip()
        self.current_user_message = text or None
        self.working_active_ref = None
        self.last_dataset_id = None
        self.turn_snapshots.clear()

    def register_query_snapshot(self, snap: QuerySnapshot) -> None:
        self.turn_snapshots.append(snap)
        self.working_active_ref = snap.result_ref
        self.last_result_ref = snap.result_ref
        self.last_dataset_id = snap.dataset_id
        self.last_resource = snap.resource
        self.last_result_rows = snap.result_rows
        self.last_rows_scanned = snap.rows_scanned


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
    analysis_context: AnalysisToolContext = field(default_factory=AnalysisToolContext)
    filter_context: "FilterContext | None" = None
    loaded_skills: set[str] = field(default_factory=set)
