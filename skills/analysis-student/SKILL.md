---
name: analysis-student
description: 个体厚报告：六章 + 五视图联动；需 student_ID 或 selected_student_ids
---

# 个体学业诊断（student granularity）

与 `data/meta/analysis_ontology.yaml` 中 `student_report_sections`、`student_diagnosis`、`trend_decline` 的 `required_sections_student` **逐字对齐**。

## required_sections（Markdown 用 `## <id>`）

1. `scope`
2. `week_trend`
3. `student_structure`
4. `question_anchors`
5. `peer_context`
6. `actions`

## 五视图（Lens）

| 章节 id | 主视图 | 说明 |
|---------|--------|------|
| week_trend | WeekView | 周 peak 走势、近 k 周对比、是否下滑 |
| student_structure | StudentView | **一章**知识树薄弱枝；勿把整棵树全文贴进报告 |
| question_anchors | QuestionView | 锚定知识点/题目得分与提交峰 |
| peer_context | ScatterView + PortraitView | cluster 位置、雷达维度、同伴对比 |

## 反模式（勿复制 ontology 全文，执行时遵守）

- 仅 StudentView visual_link 却声称完整个体诊断
- 无 week_trend 证据却断言「最近变差」
- 无 student_ID 仍走 student_diagnosis（应澄清或降为 class_overview）

## 澄清与降级

- 教师未给 `student_ID`，且 scope 无 `selected_student_ids`：**先问**或 `load_skill analysis-class` 做班级层分析
- 面板已选学生：直接用 `selected_student_ids`，勿索要学号
- 仅一名选中学生时，以该 ID 为报告主体

## 工具链（analyze / produce）

1. `inspect_schema` — `submit_record`（带 `class`）、`week_aggregation`（带 `classes`）、必要时 `student_info`
2. `query_data` — `week_aggregation` + `submit_record`（`student_ids` 或 `where` 限定目标生）
3. `aggregate_data` — `input={"result_ref": "<meta.result_ref>"}`；学生数用 `count_distinct` + `student_ID`
4. 多指标：先 `todo_write`（Workflow P，见 `data-exploration`）
5. **produce** 写报告前再 `load_skill tiered-report`（模板 A）

勿 `read_file` 原始 `Data_*.csv`。

## visual_links

- **Phase 3 前**：在 `actions` 或章节末用文字预留「应答结构：`{view, params}`」，params 对齐 `meta/visual_link_contract.yaml`
- **Phase 3 后**：分析完成后调用 `build_visual_links` 校验；WeekView 对教师只推 **一条**（params 可省略 kind）

## 交付路径（produce）

`reports/student/<student_ID>/diagnosis.md`（或短 id 子目录）

每章含：结论句 + Evidence（`metric_id` / `result_ref` 引用）+ Limitations（若有）。
