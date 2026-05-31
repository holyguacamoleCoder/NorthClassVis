---
name: analysis-student
description: 撰写个体学业诊断（点名、student_ID、变差、六章五视图）；student_diagnosis / trend_decline 个体；produce 写入 reports/student/<student_ID>/diagnosis.md。勿用于无学号的班级总览。
---

# 个体学业诊断（student granularity）

`required_sections` 与 `data/meta/analysis_ontology.yaml` 中 `student_report_sections[].id`、`required_sections_student` **逐字一致**。

## 何时使用 / 勿用

| 使用 | 勿用 |
|------|------|
| 个体、点名、诊断、peer 对比 | 全班总览 → `analysis-class` |
| Nav `selected_student_ids` 已选一名 | 无 ID 且教师未选 → **先问**或 `analysis-class` |
| produce 写 `diagnosis.md` | 纯字段探查 → `data-exploration` |

## required_sections（`## <id>`）

| id | 主视图 | 说明 |
|----|--------|------|
| `scope` | — | 班级、专业、student_ID、week_range |
| `week_trend` | WeekView | 该生周 peak；**仅 1 人** |
| `student_structure` | StudentView | 知识树薄弱枝；**勿** `report-chart` |
| `question_anchors` | QuestionView | `title_ids`；题为班级维度，须表格佐证 |
| `peer_context` | ScatterView、PortraitView | 可内嵌 |
| `actions` | — | 教学建议 |

## 反模式

- WeekView 无 `student_ids` 或含多名学生
- `read_file` `reports/` 下旧 diagnosis 当参考
- 仅 StudentView 链接却声称完整个体诊断
- 无 week_trend 证据却断言「最近变差」

面板已选学生：报告主体与图表 `student_ids` 与之相同。

## 工具链

1. `inspect_schema` — `submit_record`、`week_aggregation`、`student_info`
2. `query_data` — 限定目标生
3. `aggregate_data` — 勿用 `count` 当人数
4. 多指标：`todo_write`（见 `data-exploration`）
5. `build_visual_links` → produce：`load_skill report-delivery` → `write_file`

勿 `read_file` 原始 `Data_*.csv`。**禁止** `read_file` `reports/` 下已有文件。

## 正式报告（produce）

- **写入路径**：`reports/student/<student_ID>/diagnosis.md`
- **结构 / chart / 自检**：`load_skill report-delivery`
