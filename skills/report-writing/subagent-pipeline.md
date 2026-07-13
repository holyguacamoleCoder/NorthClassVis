# Subagent 报告流水线

> 父 Agent 编排；子循环隔离上下文，共享 `session_id` / `dataset_registry`。

## 何时委派（父 Agent）

| 场景 | 建议 |
|------|------|
| 标准 class/major 总览，≥6 章 + 多轮 query | **委派** |
| 单指标、单表查询 | 父 Agent 直接 `query_data` |
| 窄窗备忘 `<80` 行 | 父 Agent 直接写，不委派 |

## 三段子 Agent

| kind | 模式 | 产出 | 禁止 |
|------|------|------|------|
| `data_analyst` | analyze | analysis brief + refs | 写 `reports/`、嵌套 subagent |
| `report_writer` | produce | 分章 `reports/...` | 自己查数（用 brief） |
| `report_reviewer` | produce | 跨节修订 | 重写全文 |

## task 写法（传给 `run_subagent`）

每条 `task` 须含：**范围**、**交付路径**、**验收**。

**data_analyst 示例**

```
范围：Class2，week 13–15。
交付：analysis brief（不写 reports/）。
验收：含周趋势、薄弱知识点、班内分布、dataset_id/result_ref 列表。
```

**report_writer 示例**

```
范围：Class2 第 13–15 周班级总览。
依据：父消息中的 analysis brief 与 refs。
路径：reports/class/Class2/overview.md
验收：load_reference(class)；分章 write/edit；Evidence cite；[Report validate] 无 error。
```

**report_reviewer 示例**

```
路径：reports/class/Class2/overview.md
验收：review_report 跨节一致；按 fix 用 edit_file ## 整节替换；再 review 至 ok。
```

## 父 Agent 编排清单

```
- [ ] 1. run_subagent(data_analyst) — 等 tool result 中的 summary + refs
- [ ] 2. 父 Agent 整合：章节取舍、图表意图（可 build_visual_links）
- [ ] 3. run_subagent(report_writer) — task 内粘贴 brief 要点与 refs
- [ ] 4. 可选 run_subagent(report_reviewer)
- [ ] 5. 向教师交付：结论 + 报告预览链接
```

## 与直接写作的关系

- 子 Agent **不替代** `load_reference` / `report-chart` / Evidence 规范
- `report_writer` 内仍须 `load_skill(report-writing)`（produce 自动登记）与 tier reference
- 父 Agent **禁止**在子循环进行中重复查同一口径数据

## 失败处理

- `[SubAgent … FAIL]`：读 `error` + summary；父 Agent 缩小 task 重试或改为自己执行
- 子 Agent `max_turns` 用尽：拆成更小 task（先 analyst，再 writer）
