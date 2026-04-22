# Agent compiler_v1 灰度发布策略

## 目标
- 在保持接口契约不变的前提下，将主链路从 `legacy_react` 迁移到 `compiler_v1`。
- 通过可观测指标与回放样本控制风险，确保可随时回滚。

## 发布开关
- 全局模式：`AGENT_RUN_MODE`（默认 `compiler_v1`）
- 单请求覆盖：`context.agent_mode` 或 `X-Agent-Mode` / `?mode=...`
- LLM增强：`AGENT_ENABLE_LLM`（默认关闭，模板优先）

## 分阶段
1. 预发布（0%真实流量）
   - 使用 `backend/test/agent_golden_cases.json` 全量回放
   - 校验输出契约、trace 完整性、coverage/quality 字段完整性
2. 小流量（10%）
   - 保持 `AGENT_ENABLE_LLM=0`
   - 监控以下指标至少 24 小时
3. 扩容（50%）
   - 保持模板优先，可对少量请求开启 `agent_llm_enabled=true` 观察
4. 全量（100%）
   - 默认 `compiler_v1`，`legacy_react` 作为应急回滚路径保留一段时间

## 核心验收指标
- 规划有效率（可执行 plan 非空或正确澄清）>= 95%
- 范围覆盖正确率（coverage）>= 95%
- “当前数据不足以支持该结论”触发准确率 >= 95%
- 无依据结论率 <= 1%
- 平均能力调用次数较旧链路下降 >= 30%
- P95 延迟不高于基线 +15%

## 回滚策略
- 即时回滚：`AGENT_RUN_MODE=legacy_react`
- 灰度回退：仅对异常租户/班级通过 `context.agent_mode` 切回 legacy
- LLM 回退：`AGENT_ENABLE_LLM=0`，仅保留模板答案

## 运行检查清单
- 请求日志包含：`intent`、`plan_steps`、`capability_calls`、`coverage`、`quality`
- trace.steps 包含：`tool/params/summary/status/duration_ms/coverage/quality`
- 回放黄金问题时，不出现 schema 缺失或字段类型漂移
