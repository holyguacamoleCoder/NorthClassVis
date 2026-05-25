---
name: analysis-major
description: 专业跨班总览（beta）；多 classes + majors 过滤，禁止单班冒充专业结论
beta: true
---

# 专业层分析（major granularity，beta）

与 ontology `granularities.major` 对齐；**实验性**，跨班可比性有限。

## required_sections（建议骨架，Markdown `## <id>`）

1. `scope`
2. `week_trend`
3. `question_anchors`
4. `distribution`（跨班汇总）
5. `actions`

可选：`typical_classes` — 哪些班拖累/领先（勿与单班 overview 混为一谈）

## 范围与过滤

- `majors` + 多个 `classes`：`submit_record` 上传 `majors=["J23517"]` 及所需 `classes`
- `student_info` 按 `major` 字段；**勿**把专业码写入 `student_ID`
- 禁止把 **单班** Class1 结论直接标为「专业 J23517 结论」——须显式多班证据或说明仅单班可得

## Lens 与局限

- primary：week、question（跨班聚合）
- portrait / cluster：**跨班可比性局限** — 聚类在不同班混合时仅作探索性描述，勿过度解读排名
- StudentView：n/a 作为主路径；个体仅作 drill-down

## 工具链

同 `analysis-class`，但 query 必须带 `majors`（及多 `classes` 若教师指定）。

## 交付路径（produce）

`reports/major/<major>/overview.md`

写报告前 `load_skill tiered-report`（模板 C，beta）。
