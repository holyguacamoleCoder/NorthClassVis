# Class Report Reference

> 通用规则见 [_shared.md](_shared.md)。

适用：`reports/class/<ClassN>/overview.md`

## Required Sections

| id | 要点 |
|----|------|
| scope | 班级、时间窗、人数 |
| summary | 核心发现 |
| week_trend | 班级趋势（聚合统计为主；WeekView 仅 2–3 代表生） |
| question_anchors | 薄弱题目/知识点 |
| distribution | 班内差异、分层 |
| actions | 发现→证据→建议 |
| evidence | cite 标签 |
| limitations | 样本与时间窗 |

可选（有数据才写）：`risk_group`、`improvement_group`、`typical_students`、`anomalies`

## 本粒度要点

- WeekView 须含 `student_ids`（2–3 代表）+ `week_range`；**不是**班均折线图
- 人数用 `count_distinct(student_ID)`，非 `count`
- 禁止仅凭均值评价班级；须结合分布与趋势

## Common Mistakes

- WeekView 仅 `week_range` 无 `student_ids`
- 用 `count` 统计选课人数
