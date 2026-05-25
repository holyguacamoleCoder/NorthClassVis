---
name: data-csv-analysis
description: [已迁移] 请 load data-exploration；本条目保留别名兼容
---

# 已迁移 → `data-exploration`

完整 resource 工作流（inspect_schema → query_data → aggregate_data、Workflow P/A/B/C、反模式表）已迁至：

**`load_skill("data-exploration")`**

## 别名要点（防旧会话断链）

- 逻辑 resource：`student_info`、`title_info`、`submit_record`、`week_aggregation`
- 勿 `read_file` 原始 `Data_*.csv`
- 统计：`query_data`（全量省略 limit）→ `aggregate_data` + `result_ref`
- 选课人数：`count_distinct` + `student_ID`

需要班级/个体/专业 **章节化报告** 时，另载 `analysis-student` / `analysis-class` / `analysis-major` 与 `tiered-report`。
