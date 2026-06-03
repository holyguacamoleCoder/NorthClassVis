# Student Report Reference

适用：

- 个体学情诊断
- 点名学生分析
- 个体阶段性评估
- reports/student/<student_ID>/diagnosis.md

目标：

帮助教师理解学生当前学习状态、知识掌握情况、变化趋势及可能的支持方向。

---

## Required Sections

以下章节必须存在（`## <id>`）：

| id                | 主视图                     | 内容         |
| ----------------- | -------------------------- | ------------ |
| scope             | -                          | 分析范围说明 |
| summary           | -                          | 核心发现     |
| week_trend        | WeekView                   | 学习趋势分析 |
| student_structure | StudentView                | 知识结构分析 |
| question_anchors  | QuestionView               | 典型问题分析 |
| peer_context      | ScatterView / PortraitView | 同伴参照     |
| actions           | -                          | 教学建议     |
| evidence          | -                          | 数据来源     |
| limitations       | -                          | 分析限制     |

---

## Analysis Priorities

个体报告优先关注：

### Learning Trend

学生近期状态是否发生变化？

关注：

- 持续提升
- 持续下降
- 波动变化

必须有 week_trend 证据支撑。

禁止：

无趋势数据直接描述：

- 最近变差
- 最近进步明显

---

### Knowledge Structure

学生薄弱知识点在哪里？

关注：

- 知识树薄弱分支
- 长期薄弱区域
- 重复出现的问题

StudentView 用于支撑此部分。

---

### Question Anchors

哪些具体题目最值得关注？

关注：

- 错误率较高题目
- 重复错误题目
- 代表性问题

必须配套表格或统计证据。

---

### Peer Context

学生处于什么位置？

关注：

- 同班对比
- 同专业对比
- 分布位置

避免仅给出排名。

推荐结合群体分布解释。

---

### Teaching Suggestions

建议必须对应前文发现。

格式：

发现 → 证据 → 建议

禁止与前文无关的泛化建议。

---

## Visualization Requirements

### week_trend

必须包含：

- week_aggregation
- WeekView

要求：

- WeekView 中仅包含目标学生
- 必须提供 student_ids
- 必须提供 week_range

限制：

- student_ids 数量必须为 1

---

### student_structure

必须包含：

- StudentView

用途：

- 展示知识结构
- 定位薄弱分支

注意：

StudentView 为结构证据。

不是趋势证据。

不得用于判断：

- 最近变好
- 最近变差

---

### question_anchors

必须包含：

- QuestionView

同时必须提供：

- **title_ids**：须为 `inspect_schema` / `query_data` 得到的 **`title_ID`**（形如 `Question_…`），**禁止**把知识点短码（如 `b3C9s`、`r8S3g`）写入 `title_ids` 或正文「题目 ID」
- 若仅有知识点：正文写「知识点」，`report-chart` 用 `knowledge` 或 `knowledge_ids`，勿冒充题目
- 对应统计表（错题次数、均分等）

禁止：

仅凭图表描述问题；禁止「题目 ID」与知识点混用。

---

### peer_context

推荐：

- ScatterView
- PortraitView

用于展示：

- 群体位置
- 同伴参照

允许：

report-chart

---

## Chart Constraints

### WeekView

要求：

- 仅允许目标学生
- student_ids 数量必须为 1

禁止：

- 多学生 WeekView
- 缺失 student_ids

---

### StudentView

禁止 report-chart。

仅允许：

- build_visual_links

---

### QuestionView

允许：

- report-chart
- build_visual_links

---

### ScatterView

允许：

- report-chart
- build_visual_links

---

### PortraitView

允许：

- report-chart
- build_visual_links

---

## Diagnostic Reasoning Rules

允许：

“最近 4 周完成度持续下降”

前提：

存在 week_trend 证据

---

允许：

“知识点 A、B、C 掌握较弱”

前提：

存在 StudentView 或题目统计证据

---

禁止：

“学习兴趣下降”

“学习态度较差”

“缺乏主动性”

“缺少学习动力”

除非有明确可观测指标支持。

---

禁止：

将行为现象直接解释为心理原因。

---

## Scope Rules

必须明确说明：

- student_ID
- class
- major
- week_range

分析对象必须唯一。

---

## Tool Chain

推荐流程：

1. inspect_schema
   - submit_record
   - week_aggregation
   - student_info

2. query_data
   - 限定目标学生

3. aggregate_data

4. build_visual_links

5. write_file

---

## Limitations Requirements

必须说明：

1. 时间窗口限制
2. 数据覆盖范围
3. 指标缺失情况
4. 诊断结果仅反映当前观测数据

---

## Common Mistakes

### Wrong

WeekView 无 student_ids

### Wrong

WeekView 包含多名学生

### Wrong

仅提供 StudentView 即完成个体诊断

### Wrong

无趋势证据却断言最近变差

### Wrong

将行为数据解释为学习态度问题

### Wrong

仅给出排名而无群体参照

### Wrong

read_file 旧 reports/student/\*\* 作为参考

每次诊断必须基于当前查询结果重新生成。
