# Class Report Reference

适用：

- 班级学情总览
- 班级阶段性诊断
- reports/class/<ClassN>/overview.md

目标：

帮助教师快速了解班级整体学习状态、变化趋势、主要薄弱点及教学干预方向。

---

# Required Sections

以下章节必须存在：

| id                 | 内容                   |
| ------------------ | ---------------------- |
| `scope`            | 分析范围说明           |
| `summary`          | 核心发现（先结论）     |
| `week_trend`       | 班级周趋势分析         |
| `question_anchors` | 主要知识点或题目薄弱项 |
| `distribution`     | 班级内部差异分析       |
| `actions`          | 教学建议               |
| `evidence`         | 数据来源               |
| `limitations`      | 分析限制               |

---

# Optional Sections

当数据支持时允许增加：

| id                  | 触发条件             |
| ------------------- | -------------------- |
| `risk_group`        | 出现明显低表现群体   |
| `improvement_group` | 出现明显进步群体     |
| `comparison`        | 存在班级间比较       |
| `typical_students`  | 需要展示代表性案例   |
| `anomalies`         | 存在异常波动或极端值 |

禁止为了模板完整性强行生成。

---

# Analysis Priorities

推荐按以下顺序组织分析：

## 1. Overall Status

班级整体表现如何？

关注：

- 平均水平
- 活跃度
- 完成情况

---

## 2. Trend Analysis

班级状态是否发生变化？

关注：

- 持续提升
- 持续下降
- 剧烈波动

WeekView 可作为趋势佐证。

注意：

WeekView 展示的是学生周活动格子图。

不是班级均值趋势图。

---

## 3. Weak Knowledge Areas

关注：

- 低正确率题目
- 高频错误题目
- 持续性薄弱知识点

推荐使用：

- QuestionView
- question_anchors

---

## 4. Distribution Analysis

关注：

- 两极分化
- 集中趋势
- 长尾学生

避免仅根据平均值下结论。

必须结合分布证据。

---

## 5. Action Suggestions

建议必须对应前文发现。

格式：

发现 → 证据 → 建议

禁止直接给出无证据支持的教学建议。

---

# Visualization Guidance

## WeekView

用途：

展示代表性学生的周学习活动。

要求：

- 必须提供 student_ids
- 必须提供 week_range

推荐：

2~3 名代表学生。

WeekView 不用于展示班级均值趋势。

---

## QuestionView

用途：

展示薄弱题目或知识点。

适用于：

- 错误率分析
- 知识点诊断

---

## Aggregate Distribution

用途：

展示班级内部差异。

适用于：

- 分层分析
- 风险群体识别

---

# Typical Students

仅在以下情况推荐：

- 需要展示典型案例
- 需要解释班级现象

要求：

- 2~3 名学生
- 必须与 WeekView student_ids 保持一致

禁止展示大量学生个体信息。

---

# Common Mistakes

## Wrong

WeekView 仅提供 week_range

原因：

无法定位学生活动数据。

---

## Wrong

使用 count 统计学生人数

正确：

count_distinct(student_ID)

---

## Wrong

仅根据平均值认定班级优秀或落后

正确：

结合分布与趋势分析。

---

## Wrong

根据表现直接推断学习态度

例如：

- 学习积极
- 学习懈怠
- 学习兴趣不足

除非数据明确支持。

---
