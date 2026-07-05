---
name: report-writing
description: >
  生成并写入 reports/ 下教育分析 Markdown（含 report-chart 与教学建议）。
  用于学情诊断、班级总览、专业分析、专题备忘、数据解读。
  produce 模式自动加载；标准报告须 load_reference(student|class|major|freeform)。
---

# Report Writing

通用规则：[references/_shared.md](references/_shared.md)（与 tier reference 一并遵守）。

## Workflow

- [ ] 1. **Identify scope** — student / class / major / freeform；与 query 范围一致
- [ ] 2. **load_reference** — 标准报告必加载对应 tier（禁止跳过）
- [ ] 3. **Discover insights** — 趋势 / 对比 / 分布 / 异常；数据驱动增删章节
- [ ] 4. **build_visual_links** — 分析结论对应的图表 params；`report-chart` 与之完全一致
- [ ] 5. **分章写入** — 见下方「分章续写」
- [ ] 6. **Evidence + Limitations** — 末章含 cite 标签
- [ ] 7. 确认 `[Report validate]` 无 error

## Scope → Reference

| Scope | load_reference |
|-------|----------------|
| Student | `student` |
| Class | `class` |
| Major | `major` |
| Freeform | `freeform` |

## 分章续写（produce）

目标篇幅约 **120–180 行**（由 `report_quality_rules.yaml` 校验）。

| 轮次 | 工具 | 内容 |
|------|------|------|
| 1 | `write_file` | 标题 + 全部 `## <id>` 标题 + `scope` / `summary` 首稿 |
| 2…n | `edit_file` | 按 tier reference 顺序填充各分析章 |
| 末 | `edit_file` | `evidence`（cite 标签）、`limitations` |

分章 `edit_file`：`old_text` 首行写 `## <章节标题>` 即可**整节替换**（正文不必与文件完全一致）；精确替换时须与 `read_file` 原文一致。postprocess 自动改图后请先 `read_file` 或继续用 `##` 整节替换。

禁止整篇重写（除非 validate 报大量 error）；禁止 `read_file` 旧 `reports/`。

## 标准路径

| 粒度 | 路径 |
|------|------|
| Student | `reports/student/<student_ID>/diagnosis.md` |
| Class | `reports/class/<ClassN>/overview.md` |
| Major | `reports/major/<major>/overview.md` |
| 备忘/专题 | `reports/notes/<topic>.md` |

文件名：小写、连字符。

## 数据与文件

- 数字仅来自 `query_data` / `aggregate_data`；禁止编造
- 仅写入 `reports/**`；禁止写 `Data_*.csv`、`Data_SubmitRecord/**`

## 写入前检查

1. 路径在 `reports/`
2. scope 与 reference 已加载
3. `build_visual_links` 已完成且与 report-chart 一致
4. 数值来自本轮查询
5. 含 `## Evidence`、`## Limitations`
