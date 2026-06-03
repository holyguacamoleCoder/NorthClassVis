# Major Report Reference

适用：

- 跨班专业总览
- 专业阶段性学情分析
- reports/major/<major>/overview.md

目标：

从专业层面识别整体趋势、共性问题与班级差异，为专业建设和教学决策提供依据。

---

## Required Sections

以下章节必须存在（`## <id>`）：

| id               | 内容                 |
| ---------------- | -------------------- |
| scope            | 分析范围与聚合说明   |
| summary          | 核心发现（先结论）   |
| week_trend       | 专业整体趋势         |
| question_anchors | 专业共性薄弱点       |
| distribution     | 班级间与专业内部分布 |
| actions          | 教学建议             |
| evidence         | 数据来源             |
| limitations      | 分析限制             |

可选：

- typical_classes
- risk_groups
- improvement_groups
- anomalies

仅在数据支持时生成。

---

## Analysis Priorities

专业报告优先关注：

### Overall Status

专业整体表现如何？

关注：

- 学习表现
- 活跃情况
- 完成情况

---

### Cross-Class Trend

不同班级是否呈现一致变化趋势？

关注：

- 普遍提升
- 普遍下降
- 班级分化

---

### Shared Weak Areas

哪些知识点或题目在多个班级中反复出现？

优先关注：

- 多班共同薄弱项
- 多班共同错误模式

---

### Distribution Analysis

专业内部是否存在明显差异？

关注：

- 班级差异
- 学生分层
- 风险群体

避免仅依据均值分析。

---

## Visualization Requirements

### week_trend

必须包含：

- week_aggregation
- aggregate_data

可选：

- WeekView（案例展示）

要求：

- 趋势结论来源于聚合统计
- WeekView仅用于辅助解释

禁止：

仅依据WeekView得出专业趋势结论

---

### question_anchors

必须包含：

- QuestionView

用于展示：

- 共性薄弱题目
- 共性知识点

要求：

问题至少在多个班级中出现。

---

### distribution

必须包含：

- aggregate_data分布统计

可选：

- ScatterView

用于展示：

- 班级差异
- 学生分层
- 风险群体

禁止：

仅依据平均值评价专业表现。

---

### actions

每条建议必须关联：

发现 → 证据 → 建议

建议必须能够追溯到前文数据。

---

## Chart Constraints

### WeekView

允许：

- report-chart
- build_visual_links

限制：

- 全文最多 1 个 WeekView
- 代表学生总数 ≤ 6
- 必须同时提供 student_ids 与 week_range

注意：

WeekView 是学生行为案例图。

不是专业统计趋势图。

---

### QuestionView

允许：

- report-chart
- build_visual_links

优先用于：

- 共性弱项分析
- 题目诊断

---

### StudentView

禁止 report-chart。

仅允许：

- build_visual_links

---

### PortraitView

禁止 report-chart。

仅允许：

- build_visual_links

---

## Scope & Filtering Rules

必须明确说明：

- majors
- classes
- week_range

以及：

- 纳入班级数量
- 纳入学生数量
- 聚合方式

例如：

“本报告基于软件工程专业3个班级、126名学生的数据生成。”

查询时：

- submit_record 传入 majors 与所需 classes
- 不得将专业码写入 student_ID

---

## Cross-Class Reasoning Rules

允许：

多个班级均表现出相同问题

↓

形成专业级结论

---

允许：

部分班级出现问题

↓

表述为：

- 部分班级存在……
- 个别班级表现出……

---

禁止：

单班现象直接上升为专业结论

---

禁止：

未说明聚合方式却进行专业层比较

---

## Limitations Requirements

必须说明：

1. 跨班样本差异
2. 数据时间窗口限制
3. 课程覆盖差异
4. 跨班可比性限制

若纳入班级较少：

必须说明专业结论代表性有限。

---

## Common Mistakes

### Wrong

未说明跨班聚合方式却下专业级定论

### Wrong

仅依据 WeekView 推断专业趋势

### Wrong

WeekView 代表学生超过 6 人

### Wrong

使用 StudentView 或 PortraitView 作为 report-chart

### Wrong

将局部班级现象描述为专业普遍现象

### Wrong

仅依据平均值判断专业整体表现
