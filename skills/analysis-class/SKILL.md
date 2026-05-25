---
name: analysis-class
description: 班级层分析：Week/Question 为主，Portrait 为辅；对齐 Class1 样例结构
---

# 班级学业总览（class granularity）

与 ontology `class_overview`、`trend_decline_class` 及样例 `data/reports/academic_analysis_Class1.md`、`_reference.md` 对齐。

## required_sections（Markdown 用 `## <id>`）

1. `scope`
2. `week_trend`
3. `question_anchors`
4. `distribution`
5. `typical_students`（可选，2–3 名代表）
6. `actions`

## Lens 优先级

- **primary**：WeekView、`week_aggregation`；QuestionView、知识点弱项 TOP
- **secondary**：StudentView（代表学生 drill-down）；PortraitView（班内 cluster 画像）
- scatter 非班级主路径，勿当全班结论唯一依据

## 各章要点

| id | 内容 |
|----|------|
| scope | 班级名（如 Class1）、周窗、filter（classes / week_range） |
| week_trend | 班均/分层周趋势；resource `week_aggregation` + `classes` |
| question_anchors | 知识点 TOP 弱项、题目锚点；`submit_record` + aggregate |
| distribution | 得分/状态分布（`aggregate_data`：count、mean、按 state/score 分组） |
| typical_students | 可选 2–3 名：高分/低分/波动代表；secondary Student lens，非全文树 |
| actions | 教学建议，可映射 HTTP `actions[]` |

## 工具链

1. `inspect_schema` — `submit_record`、`week_aggregation`（均带 `class` 或 `classes`）
2. `query_data` — `week_aggregation`；`submit_record` + `class="ClassN"`
3. `aggregate_data` — 全班统计用 **omit limit** 的 `result_ref`；分布用 `dimensions`
4. 写正式报告：`load_skill tiered-report`（模板 B）→ `write_file`

## 反模式

- 用单班样本断言专业/全校结论 → 改用 `analysis-major`
- `count` 当选课人数 → `count_distinct` + `student_ID`
- 无 week 证据断言「班级变差」

## 交付路径（produce）

`reports/class/<ClassN>/overview.md`

参考基准：`data/reports/academic_analysis_Class1_reference.md`（全量统计口径）；agent 产出勿夸大「得分优秀」类结论而无分布证据。
