---
name: report-writing
description: >
  生成并写入 reports/ 下教育分析 Markdown（含 report-chart 与教学建议）。
  用于学情诊断、班级总览、专业分析、专题备忘、数据解读。
  produce 模式自动加载；标准报告须 load_reference(student|class|major|freeform)。
  长报告（多章、多轮查数）优先 run_subagent 流水线：data_analyst → report_writer → report_reviewer。
---

# Report Writing

通用规则：[references/_shared.md](references/_shared.md)。Subagent 编排：[subagent-pipeline.md](subagent-pipeline.md)。

## 选路径：直接写 vs Subagent

| 条件 | 路径 |
|------|------|
| 窄窗备忘、单指标、<80 行 | 父 Agent 直接 query → write/edit |
| 标准 tier 总览、≥6 章、多轮 aggregate | **Subagent 流水线**（见下） |
| 仅修订已有稿 | `review_report` 或 `report_reviewer` |

## Workflow（直接写作）

- [ ] 1. **Identify scope** — student / class / major / freeform；与 query 范围一致
- [ ] 2. **load_reference** — 标准报告必加载对应 tier（禁止跳过）
- [ ] 3. **Discover insights** — 趋势 / 对比 / 分布 / 异常
- [ ] 4. **build_visual_links** — 与 `report-chart` params 完全一致
- [ ] 5. **分章写入** — 见「分章续写」
- [ ] 6. **Evidence + Limitations**
- [ ] 7. **review_report** — 跨节一致性；按 fix `edit_file` `## <id>` 整节替换
- [ ] 8. `[Report validate]` 无 error

## Workflow（Subagent 流水线）

父 Agent 编排；子循环仅经 `run_subagent` 返回 summary + refs（详见 [subagent-pipeline.md](subagent-pipeline.md)）。

- [ ] 1. `run_subagent(kind=data_analyst)` — brief + refs，**不写** reports/
- [ ] 2. **父 Agent 整合** — 章节结构、图表意图；必要时 `build_visual_links`
- [ ] 3. `run_subagent(kind=report_writer)` — task 含 brief、路径、验收
- [ ] 4. 可选 `run_subagent(kind=report_reviewer)` — 跨节修订
- [ ] 5. 向教师交付结论 + 报告链接

**禁止**：子 Agent 嵌套 `run_subagent`；`report_writer` 在未收到 brief 时自行大范围查数。

## Scope → Reference

| Scope | load_reference |
|-------|----------------|
| Student | `student` |
| Class | `class` |
| Major | `major` |
| Freeform | `freeform` |

## 分章续写（produce）

目标篇幅约 **120–180 行**（`report_quality_rules.yaml`）。

| 轮次 | 工具 | 内容 |
|------|------|------|
| 1 | `write_file` | 标题 + 全部 `## <id>` + `scope` / `summary` |
| 2…n | `edit_file` | 按 tier reference 填充各章 |
| 末 | `edit_file` | `evidence`、`limitations` |
| 修订 | `review_report` 或 `report_reviewer` | issues 清单，非全文 |

`edit_file`：`old_text` 首行 `## <章节名>` 即**整节替换**。修订阶段优先 `review_report`，避免 `read_file` 整篇。

禁止整篇重写；禁止 `read_file` 旧 `reports/`（修订当前会话同一路径除外）。

## 标准路径

| 粒度 | 路径 |
|------|------|
| Student | `reports/student/<student_ID>/diagnosis.md` |
| Class | `reports/class/<ClassN>/overview.md` |
| Major | `reports/major/<major>/overview.md` |
| 备忘/专题 | `reports/notes/<topic>.md` |

## 数据与文件

- 数字仅来自 `query_data` / `aggregate_data`（或 data_analyst 返回的 refs）
- 仅写入 `reports/**`；禁止写 `Data_*.csv`

## 写入前检查

1. 路径在 `reports/`
2. scope 与 reference 已加载（report_writer 子 Agent 内完成）
3. `build_visual_links` 与 report-chart 一致
4. 含 `## Evidence`、`## Limitations`
