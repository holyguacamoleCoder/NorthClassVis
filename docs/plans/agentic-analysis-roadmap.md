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
| 1 | `feat/data-resource-registry` | `resource` id → 路径/loader；依赖 Phase 0 的 resource 字符串 |
| 2 | `feat/tabular-query-primitive` | query/aggregate → tabular_result + result_ref |
| 3 | `feat/generic-agent-tools` | inspect_schema、filter_context；停增业务名 tool |
| 4 | `feat/metrics-runtime` | 按 metrics 定义计算并写入 evidence |
| 5 | `feat/analysis-orchestrator` | archetype → 子目标 → 工具序列 |
| 6 | `feat/thick-student-delivery` | 六章 + 五视图；Portrait/Scatter handler |
| 7 | `feat/agentic-analysis-e2e` | 薄包装旧 tool；golden 全绿 |

各 `feat/*` 合入 `epic/agentic-analysis`。Phase 1 不改 archetype 语义，冲突先改契约再写代码。

参考：`backend/test/test_agent_contract.py`、`frontend/src/App.vue`、`data/meta/data_catalog.md` §7
