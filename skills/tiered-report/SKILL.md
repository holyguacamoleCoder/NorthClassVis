---
name: tiered-report
description: 三套 Markdown 报告骨架（student / class / major）与 data/reports 路径规范
---

# Tiered Report Templates

由 `report-markdown` 演进。写 **正式学业报告** 前应先 `load_skill` 对应 `analysis-*`，再加载本 skill。

## 路径规范（相对 `data/`）

| 粒度 | 路径 |
|------|------|
| student | `reports/student/<student_ID>/diagnosis.md` |
| class | `reports/class/<ClassN>/overview.md` |
| major (beta) | `reports/major/<major>/overview.md` |

- 仅写入 `reports/` 或 `exports/`（produce 模式）
- **禁止**修改 `Data_*.csv`

## Evidence 引用方式

- 正文引用统计时注明：`metric_id`（见 `data/meta/metrics/_index.yaml`）或 `result_ref` / `dataset_id` 来自哪次 `query_data`
- 数字须与 `aggregate_data` 输出一致；有 `meta.warnings` 须在 Limitations 说明

---

# 模板 A — student

章节 id 与 ontology **逐字一致**：

```markdown
# <学生短名或 ID> 学业诊断

## scope
班级、专业、student_ID、时间窗、数据范围说明。

## week_trend
WeekView 证据：peak 走势、近 k 周、是否下滑。

## student_structure
StudentView 一章：薄弱知识点/状态模式（勿贴全文树）。

## question_anchors
QuestionView：锚定题目/知识点与得分。

## peer_context
ScatterView + PortraitView：cluster、雷达、同伴对比。

## actions
教学建议；可附 visual_links 占位或 build_visual_links 结果。

## Overview
（可选置顶摘要段：3–5 句总览）

## Evidence
- metric_id / result_ref 列表

## Limitations
抽样、warnings、缺失字段。

---
NorthClassVision · 勿改 Data_* 原始文件
```

---

# 模板 B — class

```markdown
# <ClassN> 学业总览

## scope
班级、周窗、filter。

## week_trend
班均周趋势（week_aggregation）。

## question_anchors
知识点 TOP 弱项。

## distribution
得分/状态分布（aggregate）。

## typical_students
可选 2–3 名代表（secondary Student lens）。

## actions
教学建议。

## Overview
## Evidence
## Limitations

---
NorthClassVision · 勿改 Data_* 原始文件
```

---

# 模板 C — major（beta）

```markdown
# 专业 <major> 跨班总览（beta）

## scope
majors、涉及 classes、时间窗。

## week_trend
跨班周趋势（说明多班合并方式）。

## question_anchors
跨班知识点弱项。

## distribution
跨班得分/状态分布。

## actions
专业层建议；勿将单班结论标为专业定论。

## Overview
## Evidence
## Limitations
含 Portrait/cluster 跨班可比性局限。

---
NorthClassVision · beta · 勿改 Data_* 原始文件
```

## 工作流

1. 已完成 analyze 数据步（`result_ref` 就绪）
2. `todo_write` 多章报告时按章勾选 acceptance
3. `write_file` 到上表路径；长报告用 `edit_file` 增补
4. 需要 schema 时 `read_file` 仅 `meta/`、`reports/`（非 CSV）
