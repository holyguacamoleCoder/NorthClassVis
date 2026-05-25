# Agentic 学业分析路线图

集成分支：`epic/agentic-analysis` · 架构：工具=执行器，模型=规划器 · 双轴 Granularity×Lens

## 契约文件（Phase 0，已冻结）

| 文件 | 用途 |
|------|------|
| `data/meta/analysis_ontology.yaml` | 粒度、Lens 矩阵、archetype、个体六章 |
| `data/meta/visual_link_contract.yaml` | 五视图 view/params |
| `data/meta/metrics/_index.yaml` | 指标定义 |
| `backend/agent/contracts/tabular_result.schema.json` | L4 表格返回（Phase 2+） |

## Phase 0～7

| Ph | 分支 | 要点 |
|----|------|------|
| 0 | `feat/analysis-contracts` | 上表契约；无 query_data / 新 LLM tool |
| 1 | `feat/data-resource-registry` | `resource` id → 路径/loader；注册表 `data/meta/resource_registry.yaml`；库 `backend/agent/data/` |
| 2 | `feat/agent-tools-primitives` | inspect_schema、query_data、aggregate_data；tabular_result + result_ref |
| 3 | `feat/generic-agent-tools` | filter_context、visual_links 薄适配；停增业务名 tool |
| 4 | `feat/skills-analysis-tiers` | analysis-* / data-exploration / tiered-report skills；别名保留 |
| 4b | `feat/metrics-runtime` | 按 metrics 定义计算并写入 evidence |
| 5 | `feat/analysis-orchestrator` | archetype → 子目标 → 工具序列 |
| 6 | `feat/thick-student-delivery` | 六章 + 五视图；Portrait/Scatter handler |
| 7 | `feat/agentic-analysis-e2e` | 薄包装旧 tool；golden 全绿 |

各 `feat/*` 合入 `epic/agentic-analysis`。Phase 1 不改 archetype 语义，冲突先改契约再写代码。

参考：`backend/test/test_agent_contract.py`、`frontend/src/App.vue`、`data/meta/data_catalog.md` §7

## Phase 1 验收（`feat/data-resource-registry`）

- [x] `data/meta/resource_registry.yaml` — `student_info`、`title_info`、`submit_record`、`submit_record_joined`、`week_aggregation`
- [x] `backend/agent/data/` — `resolve`、`loaders`、`derived`、`limits`、`tabular`、`FilterContext`
- [x] `backend/test/test_resource_registry.py` — join / series / truncated / 异常
- [x] metrics `_index.yaml` 引用的 resource id 均可 `resolve`
- [ ] 无新增 LLM TOOLS（本 Phase 不注册 tool schema）

## Phase 2 验收（`feat/agent-tools-primitives`）

- [x] `backend/agent/data/` — `where`、`query`、`aggregate`、`result_store`、`inspect`
- [x] LLM 工具 `inspect_schema`、`query_data`、`aggregate_data`（schema + registry + modes）
- [x] 大结果 preview + `meta.truncated` + `meta.result_ref`（`backend/.agent/task_outputs/query-results/`）
- [x] `consult` 仅 `inspect_schema`；`analyze`/`produce` 含 query/aggregate
- [x] `backend/agent/test/test_data_tools.py`
- [ ] Phase 3：`get_current_filter_context`、`build_visual_links`（见 Phase 3 验收）

## Phase 3 验收（`feat/generic-agent-tools`）

- [ ] `backend/agent/data/filter_context.py` — `from_http_body`、`merge_defaults`、`to_dict`
- [ ] `backend/agent/data/visual_links.py` — 校验/规范化（读 `visual_link_contract.yaml`）
- [ ] LLM 工具 `get_current_filter_context`、`build_visual_links`（manifest + modes）
- [ ] `LoopState.filter_context` + executor 自动注入 `query_data`/`inspect_schema`
- [ ] consult 仅 `get_current_filter_context`；analyze/produce 含两者
- [ ] `backend/agent/test/test_adapter_tools.py`
- [ ] 无新增第四类「分析」业务工具

**本 Phase 不做**：Orchestrator 自动填 HTTP 顶层 `visual_links[]`、PortraitView 前端 handler、analysis skills（P4/P6/P7）

## Phase 4 验收（`feat/skills-analysis-tiers`）

- [x] `skills/analysis-student|class|major|data-exploration|tiered-report/SKILL.md` — SkillRegistry 可发现
- [x] `analysis-student` 六章 id 与 `analysis_ontology.yaml` `student_report_sections` 逐字一致
- [x] `analysis-student` 含五视图 + 反「仅 Student 树」；`analysis-class` 含 distribution / typical_students
- [x] `tiered-report` 含 student / class / major 三套 `##` 骨架
- [x] `report-markdown`、`data-csv-analysis` 保留别名，`load_skill` 含迁移提示
- [x] `backend/agent/common/prompts.py` — 「何时 load_skill」表
- [x] `py -3.11 -m pytest backend/agent/test/test_skills.py -q` 通过（自 `backend/agent` 目录）

**本 Phase 不做**：改 ontology 语义、实现 `build_visual_links` 编排、大改 `loop.py`

## Phase 2 历史（已完成）

- [x] Phase 2 原「本 Phase 不做」项已移交 Phase 3

**库层调用示例**：

```python
from data import QuerySpec, execute_query

result = execute_query(
    QuerySpec(
        resource="submit_record_joined",
        select=["student_ID", "score"],
        resolve_params={"classes": ["Class1"]},
        limit=100,
    ),
)
# LLM 侧优先 query_data，勿用业务名工具
```
