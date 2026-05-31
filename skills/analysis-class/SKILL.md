---
name: analysis-class
description: 撰写班级学业总览（ClassN、本班、班均、弱项、分布）；class_overview / trend_decline_class；produce 写入 reports/class/<ClassN>/overview.md。勿用于个体诊断或专业跨班。
---

# 班级学业总览（class granularity）

与 ontology `class_overview`、`trend_decline_class` 对齐。

## 何时使用 / 勿用

| 使用 | 勿用 |
|------|------|
| 本班、ClassN、班均、弱项 TOP、分布 | 单名学生诊断 → `analysis-student` |
| produce 写 `overview.md` | 专业/跨班定论 → `analysis-major` |
| | 仅探查字段 → `data-exploration` |

## required_sections（`## <id>`）

| id | Lens / 图表 |
|----|-------------|
| `scope` | 班级、周窗、`classes` / `week_range` |
| `week_trend` | `week_aggregation` 表 + WeekView `report-chart` |
| `question_anchors` | 弱项表 + QuestionView |
| `distribution` | aggregate 分布表 |
| `typical_students` | 可选；2–3 名代表 ID（**须**与 WeekView `student_ids` 一致） |
| `actions` | 教学建议 |

Lens：**primary** `week_aggregation` + WeekView + QuestionView；**secondary** StudentView（代表生）、PortraitView。

## 图表与数据（易混淆）

| 用途 | 工具 / 资源 | 图表 UI |
|------|-------------|---------|
| 班均/分层周趋势**数字** | `week_aggregation` + `aggregate_data` | — |
| 学生周格子图 | `report-chart` / `build_visual_links` → WeekView | `student_ids`（2–3 代表）+ `week_range` |

WeekView **不是** `week_aggregation` 折线图；无 `student_ids` 时内嵌可能空白。

## 工具链

1. `inspect_schema` — `submit_record`、`week_aggregation`
2. `query_data` — `week_aggregation`；`submit_record` + `class="ClassN"`
3. `aggregate_data` — 全班 omit limit
4. `build_visual_links` → produce：`load_skill report-delivery` → `write_file`

勿 `read_file` 原始 `Data_*.csv`。**禁止** `read_file` `reports/` 下任何已有文件。

## 反模式

- WeekView 仅 `week_range`、无 `student_ids`
- `read_file` 旧报告或 `academic_analysis_*` 当参考
- `count` 当选课人数（用 `count_distinct` + `student_ID`）
- 无分布证据夸大「得分优秀」

## 正式报告（produce）

- **写入路径**：`reports/class/<ClassN>/overview.md`（仅 `write_file`，勿 read 参考）
- **结构 / chart / 自检**：`load_skill report-delivery`（`skills/reference/report-delivery.md`）
