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
| 4 | `feat/metrics-runtime` | 按 metrics 定义计算并写入 evidence |
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
- [ ] Phase 3：`get_current_filter_context`、`build_visual_links`（本 Phase 不做）

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
