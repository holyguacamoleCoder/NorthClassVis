#!/usr/bin/env python3
"""PermissionDeny: inject teacher-facing hints after permission denies a tool call."""

from __future__ import annotations

import sys

from _lib import (
    hook_deny_reason,
    hook_deny_type,
    hook_event,
    hook_permission_mode,
    hook_tool_input,
    hook_tool_name,
    is_deliverable_path,
    normalize_data_path,
)

WRITE_TOOLS = frozenset({"write_file", "edit_file"})
RAW_DATA_READ_HINT = (
    "原始学业 CSV 已禁止 read_file。consult：inspect_schema；"
    "analyze/produce：query_data（如 submit_record + class='Class1' 或 majors=['J23517']）。"
    "启动或输入 /mode analyze 以启用 query_data。"
)
CONSULT_NO_READ_FILE_HINT = (
    "consult 模式不提供 read_file。探查表结构/样例请用 inspect_schema；"
    "统计请 /mode analyze 后使用 query_data。"
)


def main() -> None:
    if hook_event() != "PermissionDeny":
        sys.exit(0)

    tool = hook_tool_name()
    mode = hook_permission_mode()
    deny_type = hook_deny_type()
    reason = hook_deny_reason()
    tool_input = hook_tool_input()
    path = normalize_data_path(str(tool_input.get("path") or ""))

    if tool == "read_file" and mode == "consult":
        print(CONSULT_NO_READ_FILE_HINT, file=sys.stderr)
        sys.exit(2)

    if tool == "read_file" and ("query_data" in reason or "inspect_schema" in reason):
        print(RAW_DATA_READ_HINT, file=sys.stderr)
        sys.exit(2)

    if tool not in WRITE_TOOLS:
        sys.exit(0)

    if mode in ("consult", "analyze"):
        msg = (
            f"当前为 **{mode}** 模式，不能写入或修改文件（包括 reports/、exports/）。\n"
            "若需要生成/更新分析报告，请在 CLI 输入 `produce` 切换到 **produce** 模式后重试；\n"
            "或先在当前模式下给出分析结论，暂不写入交付文件。"
        )
        print(msg, file=sys.stderr)
        sys.exit(2)

    if mode == "produce" and path and not is_deliverable_path(path):
        msg = (
            "produce 模式下，分析交付物只能写入 `reports/` 或 `exports/`（相对 data/）。\n"
            f"本次路径：`{path or '(empty)'}`。\n"
            "请改用例如 `reports/academic_analysis_Class1.md`。"
        )
        print(msg, file=sys.stderr)
        sys.exit(2)

    if deny_type == "approval" and tool in WRITE_TOOLS:
        msg = (
            "写入操作需要教师确认，本次未批准。\n"
            "可在交互式 CLI 中批准，或切换到更高能力模式（produce）并调整权限规则。"
        )
        print(msg, file=sys.stderr)
        sys.exit(2)

    if "write operations are blocked" in reason.lower() and mode:
        msg = (
            f"模式 **{mode}** 下禁止写操作。若要写入 reports/，请切换到 **produce**。"
        )
        print(msg, file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
