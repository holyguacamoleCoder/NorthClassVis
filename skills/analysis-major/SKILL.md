---
name: analysis-major
description: 撰写专业跨班总览 beta（majors、多班弱项）；produce 写入 reports/major/<major>/overview.md；Limitations 须写跨班可比性。勿用于单班 ClassN 或个体诊断。
beta: true
---

# 专业层分析（major granularity，beta）

与 ontology `granularities.major` 对齐；跨班可比性有限。

## 何时使用 / 勿用

| 使用 | 勿用 |
|------|------|
| majors、跨班、专业整体 | 单班 ClassN → `analysis-class` |
| produce 写 `reports/major/.../overview.md` | 个体诊断 → `analysis-student` |

## required_sections（`## <id>`）

| id | 说明 |
|----|------|
| `scope` | majors、classes、week_range、合并说明 |
| `week_trend` | 跨班周统计 + WeekView |
| `question_anchors` | 跨班弱项 + QuestionView |
| `distribution` | 跨班分布表 |
| `actions` | 教学建议 |

可选：`typical_classes`。

## 范围与过滤

- `submit_record` 传 `majors` + 所需 `classes`
- **勿**把专业码写入 `student_ID`
- 禁止单班结论标为专业定论

## Lens 与图表

- **primary**：`week_aggregation` + `majors`
- WeekView：1 条；代表生合计 **≤6**
- StudentView / Portrait：**勿** `report-chart`（仅 `build_visual_links`）

## 工具链

同 `analysis-class`，query 必须带 `majors` → `build_visual_links` → `load_skill report-delivery` → `write_file`。

**禁止** `read_file` `reports/` 下已有文件。

## 反模式

- 未写跨班合并方式却下专业级定论
- `read_file` 旧 overview 当参考
- WeekView 代表生过多（>6）

## 正式报告（produce，beta）

- **写入路径**：`reports/major/<major>/overview.md`
- **结构 / chart / 自检**：`load_skill report-delivery`；`## Limitations` 必填跨班说明
