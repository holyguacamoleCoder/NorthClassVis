---
name: report-writing

description: 生成并写入 reports/ 下的教育分析 Markdown 报告。用于学情诊断、班级总览、专业分析、专题分析、教学备忘与数据解读。支持结合可视化面板生成结构化报告。
---

# Report Writing Skill

## Purpose

根据当前分析结果生成教育分析报告。

报告应：

- 先结论后证据
- 数据驱动
- 图表支撑结论
- 支持教师快速定位问题
- 支持标准报告与自由探索报告

---

# Trigger

当用户要求：

- 输出报告
- 生成诊断
- 生成学情总览
- 生成分析文档
- 生成教学建议
- 生成数据解读
- 写入 reports/

时触发本 Skill。

---

# Workflow

执行顺序：

1. Identify Scope
2. Load Reference
3. Discover Insights
4. Plan Report Structure
5. Select Visualizations
6. Generate Report
7. Write File

---

## Step 1: Identify Scope

判断分析粒度：

- Student
- Class
- Major
- Freeform

scope 必须与 query_data 范围保持一致。
如果有对应的粒度，**必须先**调用 `load_reference` 加载对应 reference（如 `student`），再写报告正文。
禁止跳过 reference、禁止扩大分析范围。

---

## Step 2: Load Reference

写标准报告前 **必须** load_reference（个体 → `student`，班级 → `class`，专业 → `major`）。
仅按需读取，不允许全部加载。

| Scope    | Reference              |
| -------- | ---------------------- |
| Student  | references/student.md  |
| Class    | references/class.md    |
| Major    | references/major.md    |
| Mixed    | references/mixed.md    |
| Freeform | references/freeform.md |

Reference 提供推荐结构。

不是强制模板。

允许根据数据调整章节。

---

## Step 3: Discover Insights

优先发现数据中的模式：

- Trend
- Comparison
- Ranking
- Distribution
- Anomaly
- Correlation

如果发现重要模式：

允许新增对应章节。

禁止为了模板完整性强行补充内容。

---

## Step 4: Plan Report Structure

推荐结构：

### Conclusion

核心发现

### Evidence

数据证据

### Teaching Implications

教学建议

### Limitations

分析限制

可根据 Insight 增加：

- 趋势分析
- 对比分析
- 风险分析
- 异常分析
- 课程分析

---

## Step 5: Select Visualizations

图表必须服务于结论。

禁止为展示而展示。

推荐映射：

| Pattern           | View         |
| ----------------- | ------------ |
| Trend             | WeekView     |
| Ranking           | PortraitView |
| Distribution      | ScatterView  |
| Comparison        | PortraitView |
| Question Analysis | QuestionView |

约束：

- WeekView report-chart ≤ 1
- StudentView 禁止 report-chart
- 每个 report-chart 必须对应正文结论
- 不得插入无解释图表

---

## Step 6: Generate Report

写作原则：

1. 先结论后证据
2. 只描述数据支持的事实
3. 区分观察与推测
4. 不推断学生心理状态
5. 不推断未观测原因
6. 教学建议必须基于证据

禁止：

- “学生不认真”
- “缺乏学习兴趣”
- “明显态度较差”

除非数据明确支持。

---

# Data Rules

精确数字必须来自：

- query_data
- aggregate_data

不得编造。

不得引用历史报告。

不得引用未查询数据。

---

# File Rules

允许写入：

reports/\*\*

禁止写入：

Data\__.csv
Data_SubmitRecord/\*\*
exports/_.md

---

# Standard Paths

Student

reports/student/<student_ID>/diagnosis.md

Class

reports/class/<ClassN>/overview.md

Major

reports/major/<major>/overview.md

General

reports/notes/<topic>.md

或

reports/<subdir>/<filename>.md

文件名使用：

- 小写
- 连字符

---

# Report Chart Rules

语法：

```report-chart
{
  "view":"WeekView",
  "params":{}
}
```

要求：

- chart params 与 build_visual_links 完全一致
- chart 必须支撑结论
- chart 下方必须解释

---

# Required Ending Sections

所有报告必须包含：

## Evidence

列出关键数据来源。

## Limitations

说明：

- 时间窗口限制
- 样本范围限制
- 数据缺失情况
- 分析假设

---

# Write Checklist

写入前确认：

1. 目标路径位于 reports/
2. 未读取旧报告
3. scope 正确
4. reference 已按需加载
5. 每个 chart 对应结论
6. build_visual_links 参数一致
7. 数值来自本轮分析
8. 包含 Evidence
9. 包含 Limitations
10. 无未经证据支持的推断
