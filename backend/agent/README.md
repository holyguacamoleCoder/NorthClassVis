# Agent 模块（S1 教师对话）

- **接口**：`POST /api/agent/query`（请求体：`question`, `context`）；可选 `GET /api/meta/knowledge_points?q=关键词`。
- **响应**：顶层直接返回 `answer`、`evidence`、`actions`、`visual_links`、`trace`，与前端契约一致，不包 `data`。
- **LLM**：可选。设置环境变量 `OPENAI_API_KEY`（及可选 `OPENAI_BASE_URL`、`OPENAI_MODEL`）时使用 LLM 生成回答；未设置时使用规则兜底。
- **运行模式**：运行时仅使用 `compiler_v1`（意图编译 + 能力执行链路）。
- **答案生成**：模板优先，LLM增强可选。默认关闭 LLM 增强；可通过 `AGENT_ENABLE_LLM=1` 或 `context.agent_llm_enabled=true` 开启。
- **可观测字段**：`compiler_v1` 会记录 `intent`、`plan_steps`、`capability_calls`、`coverage`、`quality` 到 `agent/log/agent_llm.log`。
- **灰度发布**：执行步骤、指标与回滚方案见 `backend/agent/rollout_strategy.md`。
- **联调**：前端将 `VUE_APP_AGENT_MOCK=false` 后请求会打到本后端；可运行 `python -m pytest test/test_agent_contract.py`（需在 backend 目录且已安装依赖）校验响应契约。
