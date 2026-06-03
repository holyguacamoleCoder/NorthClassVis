#!/usr/bin/env python3
"""SessionStart: inject minimal session pointer (no duplicate resource catalog)."""

from __future__ import annotations

from _lib import write_json_stdout

# Static rules & resource table live in the agent system prompt.
# Session hook only points to mutable contracts / deliverables.
SESSION_DATA_INDEX = """## 本会话数据入口
- 结构化分析：`inspect_schema` → `query_data` → `aggregate_data`（**禁止** read_file 原始 CSV）
- 字段与契约：优先 `inspect_schema`；全貌 `read_file meta/data_catalog.md`
- **produce**：Markdown 报告仅写 `reports/`；标准 tier 用 `load_reference`（student/class/major）"""


def build_context() -> str:
    return SESSION_DATA_INDEX.strip()


def main() -> None:
    payload = {"additionalContext": build_context()}
    write_json_stdout(payload)


if __name__ == "__main__":
    main()
