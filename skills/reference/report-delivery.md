---
name: report-delivery
description: 学业报告 produce 共用规范（Markdown 结构、report-chart 白名单与 params、Evidence、写入前自检）。写 reports/ 前 load
---

# 学业报告交付规范（produce）

> 章节 id 与输出路径见各 `skills/analysis-*/SKILL.md`。`reports/`、`exports/` **仅写入产出**，禁止当作版式或数据参考。

## 写入范围

- 仅 **写入** `reports/`、`exports/`（路径相对 `data/`）
- **禁止** `read_file` 打开 `reports/`、`exports/` 下已有文件（勿抄旧报告、reference、历史 diagnosis）
- **禁止**修改 `Data_*.csv`、`Data_SubmitRecord/**`
- 契约与字段：`read_file` 仅 `meta/`（如 `analysis_ontology.yaml`、`visual_link_contract.yaml`、`data_catalog.md`）

## 报告 Markdown 结构（所有粒度）

正文用 ontology / 已加载 `analysis-*` 的 `## <id>`（禁止「## 1. 周次趋势」等编号标题）。各章写结论与表格；**Evidence / Limitations 仅文末两节**。

```markdown
# <标题>

## scope
…

## <其余 required_sections>
…（该章需要的 ```report-chart``` 插在章内）

## actions
…

## Overview
可选，一段执行摘要。

## Evidence
metric_id（`meta/metrics/_index.yaml`）或 result_ref / dataset_id。

## Limitations
meta.warnings、数据缺口、图表局限。
```

| 粒度 | 输出路径（仅写，勿 read 参考） |
|------|--------------------------------|
| 个体 | `reports/student/<student_ID>/diagnosis.md` |
| 班级 | `reports/class/<ClassN>/overview.md` |
| 专业 | `reports/major/<major>/overview.md` |

## report-chart 内嵌白名单

| 视图 | 可否 `report-chart` | 说明 |
|------|---------------------|------|
| WeekView | 是 | 选中学生的周格子；须 `week_range` |
| QuestionView | 是 | `title_ids` 1–5，与正文锚定题一致 |
| ScatterView | 是 | 同伴对比 |
| StudentView | **否** | 仅 `build_visual_links` |
| PortraitView | 是 | 该生 vs 同簇均值 |

字段形状：`meta/visual_link_contract.yaml`。

## 按粒度的 params

### 个体（analysis-student）

- WeekView（仅 1 条）：`student_ids` 仅 1 人；`week_range` 与 scope 一致
- QuestionView：`title_ids`；禁止占位 `knowledge` / `some_knowledge`
- student_structure：StudentView 仅 `build_visual_links`
- peer_context：ScatterView / PortraitView 可内嵌

### 班级（analysis-class）

- WeekView：`week_range` + `student_ids` = `## typical_students` 2–3 人
- 班均数字用 `week_aggregation`；勿与 WeekView UI 混淆
- QuestionView：`title_ids` 与弱项题一致

### 专业（analysis-major，beta）

- WeekView 代表生合计 ≤6；`## Limitations` 须写跨班合并与可比性

## report-chart 语法

在对应章节下插入（params 与 `build_visual_links` 一致；来自本轮 scope/查询）：

````markdown
```report-chart
{"view":"WeekView","params":{"student_ids":["<student_ID>"],"week_range":[<start>,<end>]}}
```
````

````markdown
```report-chart
{"view":"QuestionView","params":{"title_ids":["Question_<id1>","Question_<id2>"]}}
```
````

- 班级 `week_trend`、`question_anchors` 各至少 1 个 `report-chart`
- 仍须 `build_visual_links` 供聊天区跳转
- WeekView 全局仅 **一条**

## 写入前自检

1. 已 `load_skill` 对应 `analysis-*` 与本规范（`report-delivery`）
2. 未 `read_file` 任何 `reports/` 路径作参考
3. 每章 `## <id>` 与 ontology / analysis skill 一致
4. 数字来自本轮 aggregate
5. 文末 `## Evidence`、`## Limitations`
6. `build_visual_links` 与 `report-chart` 一致
7. 个体 WeekView 仅目标生一人
8. 班级 WeekView `student_ids` 与 `typical_students` 一致
9. 专业 Limitations 含跨班说明

## 工作流

1. analyze 完成（`result_ref` 就绪）
2. produce：`load_skill` → `analysis-*` + `report-delivery`
3. `todo_write` 按章 → `write_file` 写入目标路径（勿先读 reports/ 旧稿）
