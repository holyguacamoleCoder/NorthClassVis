---
name: data-csv-analysis
description: Read-only exploration of CSV datasets and Data_SubmitRecord under data/
---

# Data CSV Analysis Skill

Use when exploring, profiling, or summarizing **student / title / submit-record** data (including学业分析).

## Catalog vs session context

| 来源 | 内容 | 何时用 |
|------|------|--------|
| SessionStart hook | `meta/data_catalog.md` 的**摘要**（快速索引 + 策略） | 已自动注入，优先信任 |
| 本 skill | 操作流程、SubmitRecord 注意点 | `load_skill` 后按步骤执行 |
| `read_file("meta/data_catalog.md", limit=…)` | **完整**字段与关联说明 | 需要核对字段、班级命名、合并键时 |

不要把 `meta/data_catalog.md` 写到 `reports/`；那是元数据，不是交付报告。

## Policy

- `Data_*.csv` 与 `Data_SubmitRecord/**` 只读，禁止 `write_file` / `edit_file`。
- 路径相对 `data/`（如 `Data_SubmitRecord/SubmitRecord-Class1.csv`）。
- 大表必须 `limit`（建议 20–50）；SubmitRecord 单文件约 1.5–2.5 MB，按**班级**抽样，勿一次读多个全量文件。

## Datasets

- `Data_StudentInfo.csv`：`student_ID`, `sex`, `age`, `major`
- `Data_TitleInfo.csv`：`title_ID`, `score`, `knowledge`, `sub_knowledge`
- `Data_SubmitRecord/SubmitRecord-{Class}.csv`：`student_ID`, `title_ID`, `class`, `time`, `state`, `score`, `method`, `memory`, `timeconsume`（学业事实表）

**关联键**：`student_ID`、`title_ID`。

## Workflow

1. 使用 session 中的 catalog 摘要；不确定时用 `list_files` 看 `Data_SubmitRecord/` 下有哪些班级文件。
2. 对各表 `read_file` + `limit` 看表头与样例。
3. 学业报告：至少抽样 1 个 `SubmitRecord-Class*.csv`，并结合 Student/Title 表说明分布与表现。
4. 交付物用 `load_skill("report-markdown")` 后写入 `reports/<topic>/...`。

## Output

- consult / analyze：结论在对话中。
- produce：可写 `reports/<topic>/analysis.md`。
