# Skills Map

> 报告可信交付总计划：[docs/plans/report-trust-delivery.md](../docs/plans/report-trust-delivery.md)

## 目录

- `data-exploration/SKILL.md`：analyze 阶段的数据探查与聚合
- `report-writing/SKILL.md`：produce 阶段通用写作与图表规范
- `report-writing/references/*.md`：标准个体/班级/专业与 freeform 的按需细则

## 路由

1. analyze：优先 `data-exploration`
2. produce：使用 `report-writing`
3. 标准诊断/总览：按类型读取一个 references 文件（`student.md` / `class.md` / `major.md`）
4. 非标准报告：读取 `freeform.md`

## 写后校验（Phase 0+）

```bash
py scripts/validate_report.py --tier student --file data/reports/...
py scripts/validate_report.py --tier student --file path/to/report.md --json
```

契约：`data/meta/report_quality_rules.yaml`、`report_chart_protocol.yaml`、`evidence_cite_protocol.yaml`  
运行时：`backend/agent/report/validate.py`
