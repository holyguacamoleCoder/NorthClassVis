# Student Report Reference

> 通用规则见 [_shared.md](_shared.md)。

适用：`reports/student/<student_ID>/diagnosis.md`

## Required Sections（`## <id>`）

| id | 主视图 | 要点 |
|----|--------|------|
| scope | — | student_ID、class、major、week_range |
| summary | — | 核心发现（先结论） |
| week_trend | WeekView | 趋势；WeekView 仅 1 名学生 |
| student_structure | StudentView | 知识树薄弱枝（link only，无 report-chart） |
| question_anchors | QuestionView | 题目/知识点 + 统计表 |
| peer_context | ScatterView / PortraitView | 同伴参照，非仅排名 |
| actions | — | 发现→证据→建议 |
| evidence | — | cite 标签 |
| limitations | — | 时间窗、覆盖范围 |

## 本粒度要点

- **WeekView**：`student_ids` 必须为 **1** 人；须含 `week_range`
- **QuestionView**：`title_ids` 须为 `Question_…`（来自 query）；知识点用 `knowledge`/`knowledge_ids`，勿冒充题目 ID
- **StudentView**：仅 `build_visual_links`，**禁止** report-chart
- 禁止无 `week_trend` 证据却断言「最近变差」
- 禁止将行为数据解释为学习态度

## Common Mistakes

- WeekView 缺 `student_ids` 或含多名学生
- 仅有 StudentView 即声称完整个体诊断
- Evidence 无 `[@ds:…]` / `[@ref:…]` 标签
