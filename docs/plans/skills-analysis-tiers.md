# Skills 分析分层（Phase 4）维护说明

分支：`feat/skills-analysis-tiers` → 合入 `epic/agentic-analysis`

## 目录与职责

| 路径 | name | 说明 |
|------|------|------|
| `skills/analysis-student/` | analysis-student | 个体六章 + 五视图映射 |
| `skills/analysis-class/` | analysis-class | 班级层章节与 week_aggregation 辨析 |
| `skills/analysis-major/` | analysis-major | 专业跨班（frontmatter `beta: true`） |
| `skills/data-exploration/` | data-exploration | resource 完整工作流 |
| `skills/reference/report-delivery.md` | report-delivery | **SSOT**：报告结构、report-chart、Evidence、自检（经 `load_skill`） |

发现与 `SkillRegistry`：`backend/agent/skills/registry.py`（`skills/**/SKILL.md` + `skills/reference/*.md`）。

## 与 ontology 同步规则

1. **章节 id**：`analysis-student` 的 `required_sections` 必须与 `data/meta/analysis_ontology.yaml` 中 `student_report_sections[].id` 及 `required_sections_student` **逐字一致**。
2. **反模式**：从 `student_report_rules.anti_patterns` 摘录到 skill，ontology 改则同步改 skill（或开契约 PR）。
3. **archetype**：新 archetype 先改 ontology，再在对应 `analysis-*` skill 加一行映射说明。
4. **不改 ontology 语义**：Phase 4 仅文档/skill；冲突时先契约 PR 再改 skill。

## Prompt 分工

- `backend/agent/common/prompts.py`：模式边界、`何时 load_skill` 表
- `skills/reference/report-delivery.md`：报告 Markdown 结构、report-chart、自检（produce 须 `load_skill report-delivery`）
- `skills/analysis-*`：何时用、章节表、**写入**路径、粒度反模式（**不**复制 chart 细则；**禁止** read `reports/` 参考）

## 报告结构 SSOT

全文 `## <ontology_id>` + 文末 `## Overview`（可选）→ `## Evidence` → `## Limitations`。详见 `skills/reference/report-delivery.md`。

## `reports/` 政策

`data/reports/` 为**产出物目录**：Agent 仅 `write_file`/`edit_file` 写入，**禁止** `read_file` 打开已有文件作版式或数据参考（含历史 `academic_analysis_*`、旧 `overview.md`）。

## 上下文持久化（P4+）

- **已加载技能**：`session.loaded_skills` → 每轮 system prompt「已加载技能」区注入完整 SKILL 正文（单 skill 上限见 `LOADED_SKILL_BODY_PROMPT_MAX_CHARS`）
- **执行计划**：`session.todo_items` → 每轮 system prompt「当前执行计划」区注入（含 acceptance）
- `load_skill` tool 返回短确认，正文以 system prompt 为准；`micro_compact` 不压缩 `load_skill` / `todo_write` 的 tool 消息
- macro 压缩摘要模板要求保留已加载技能名与 todo 步骤

## 测试

```bash
py -3.11 -m pytest backend/agent/test/test_skills.py -q
```
