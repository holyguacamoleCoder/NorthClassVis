# Skills 分析分层（Phase 4）维护说明

分支：`feat/skills-analysis-tiers` → 合入 `epic/agentic-analysis`

## 目录与职责

| 路径 | name | 说明 |
|------|------|------|
| `skills/analysis-student/` | analysis-student | 个体六章 + 五视图 |
| `skills/analysis-class/` | analysis-class | 班级层，对齐 Class1 样例 |
| `skills/analysis-major/` | analysis-major | 专业跨班（frontmatter `beta: true`） |
| `skills/data-exploration/` | data-exploration | resource 完整工作流 |
| `skills/tiered-report/` | tiered-report | 三套 Markdown 模板 |
| `skills/data-csv-analysis/` | data-csv-analysis | 别名 → data-exploration |
| `skills/report-markdown/` | report-markdown | 别名 → tiered-report |

发现与 `SkillRegistry`：`backend/agent/skills/registry.py`（`skills/**/SKILL.md`）。

## 与 ontology 同步规则

1. **章节 id**：`analysis-student` 的 `required_sections` 必须与 `data/meta/analysis_ontology.yaml` 中 `student_report_sections[].id` 及 `required_sections_student` **逐字一致**。
2. **反模式**：从 `student_report_rules.anti_patterns` 摘录到 skill，ontology 改则同步改 skill（或开契约 PR）。
3. **archetype**：新 archetype 先改 ontology，再在对应 `analysis-*` skill 加一行映射说明。
4. **不改 ontology 语义**：Phase 4 仅文档/skill；冲突时先契约 PR 再改 skill。

## Prompt 分工

- `backend/agent/common/prompts.py`：`何时 load_skill` 表 + 工具边界
- Skill 正文：步骤、章节、路径、反模式；避免与 prompt 大段重复

## 测试

```bash
py -3.11 -m pytest backend/agent/test/test_skills.py -q
```
