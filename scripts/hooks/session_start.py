#!/usr/bin/env python3
"""SessionStart: inject slim data index into the agent session context."""

from __future__ import annotations

from _lib import write_json_stdout

# Compact session index (~600 chars). Full catalog: read_file meta/data_catalog.md in analyze/produce.
SESSION_DATA_INDEX = """# 数据索引（Session）

## 逻辑 resource（analyze：inspect_schema → query_data → aggregate_data）
| id | 用途 |
|----|------|
| student_info | 学生维度 |
| title_info | 题目维度 |
| submit_record | 提交明细（需 class 或 classes） |
| week_aggregation | 周聚合 |

## 原始资产（只读；Agent 禁止 read_file 打开）
| 资产 | 路径 |
|------|------|
| 学生 | Data_StudentInfo.csv |
| 题目 | Data_TitleInfo.csv |
| 提交 | Data_SubmitRecord/SubmitRecord-{Class}.csv |

**关联键**：student_ID、title_ID、class、major

**契约**：meta/resource_registry.yaml、meta/analysis_ontology.yaml、meta/visual_link_contract.yaml

**详情**：analyze/produce 下用 inspect_schema，或 read_file `meta/data_catalog.md`

**交付物（produce）**：仅**写入** reports/、exports/（勿 read 参考）；load `analysis-*` + `report-delivery`（skills/reference/）"""


def build_context() -> str:
    return SESSION_DATA_INDEX.strip()


def main() -> None:
    payload = {"additionalContext": build_context()}
    write_json_stdout(payload)


if __name__ == "__main__":
    main()
