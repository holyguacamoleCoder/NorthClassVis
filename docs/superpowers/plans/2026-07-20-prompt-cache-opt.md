# Prompt Cache 优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 DeepSeek/OpenAI-style prefix cache 在「同 mode、同会话」下可持续命中：system 跨 tool round 字节稳定；动态状态只进本轮新消息或 tool result；绝不回写历史。

**Architecture:** 采用 Claude Code「别改 system」+ OpenClaw「stable | volatile」思想，但落地适配当前 OpenAI-compat API（无 Anthropic `cache_control` block）：把 system 收成 **stable prefix**；volatile 按 A（本轮 user 前缀）/ B（tool result 快照）分流；micro_compact 与 report reminder 改为 cache-safe；benchmark 用真实 `cached/input` 验证，不靠永远 pass 的门禁。

**Tech Stack:** Python 3.11 agent loop（`backend/agent`）、既有 `compose_llm_user_content` / `format_turn_scope_hint`、agent benchmark harness、Langfuse usage。

## Global Constraints

- 分支：`feat/prompt-cache-opt`（仓库根 `H:/WORKDIR/NorthClassVision`）。
- **铁律：永不回写**已进入 transcript 的更早 user/assistant/tool 内容来「刷新状态」；只 append 本轮新消息或改写**尚未被上一 LLM 请求缓存住**的尾部。
- System 在同一 `permission_mode` 下跨 tool round **字节相等**（允许 mode 切换时整段换前缀并接受一次 bust）。
- 动态状态分流（与调研一致）：
  - **A（本轮 user 前缀）**：modify、当前 todo 摘要、本轮 report reminder、本轮 scope（已有）。
  - **B（tool result 快照）**：datasets catalog、deliverables 列表、loaded skill/reference 名称（随 `todo_write` / data tools / `write_file` / `load_skill` 的 result 带最新快照）。
- Provider：当前主路径 DeepSeek（无 `cache_control`）；不做 Anthropic 双 block，语义上等价于「system=稳定块」。
- 提交：仅在用户明确要求时 commit；计划中的 Commit 步骤默认跳过，改为「暂存 diff 待确认」。
- 正确性优先：cache 优化不得降低 binding / scope_contract / tool_correctness；用既有 pytest + 小规模 benchmark 回归。

## 设计锁定（来自调研 + 现状排查）

| 主题 | 决策 | 不做 |
|------|------|------|
| todo / modify | **A**：并入本轮 user（与 scope 同一 `compose` 通道） | 不写回旧 user；不进 system |
| datasets / deliverables | **B**：首轮可 A 注入一次；之后靠 tool result 尾部快照 | 不每轮改 system catalog |
| loaded_skills / refs | **B**：`load_skill` / bootstrap pin 的 tool result 已含正文；system 只保留静态「如何 load」文案 | 不在 system 列动态已加载名单（或仅首轮 A） |
| MEMORY_GUIDANCE | 并入静态 base | 勿插在动态段之后造成偏移 |
| 持久 memory 索引 | 本阶段：**仍可留在 system 末尾 volatile 区**或暂缓；优先清 todo/datasets/modify | 大改 memory 架构留 Phase 2+ |
| micro_compact | **混合**：优先只 compact「未进入上一请求前缀」的尾部；若必须改已缓存中段 → 打 `cache_bust_reason=micro_compact` 日志并接受 miss | 不在每个 tool round 无差别改写中段 |
| 全量 compact | 保持：compact LLM 调用尽量同 system+tools+history 前缀，仅末尾加 summarize；之后接受会话前缀重置 | 不在 compact 请求里先改 history |
| report reminder | **A**：只拼进本轮 user 一次，或 append 尾部独立消息；禁止 `messages[idx]=` 改写旧 user | 现状 `inject_report_continue_reminder` 回写必须删掉 |

### System 目标形状

```
[stable]
  build_base_agent_prompt(mode)
  + format_permission_mode(mode)   # 随 mode，mode 内不变
  + MEMORY_GUIDANCE                # 静态文案
  + skills catalog（注册表元数据，会话内不变）
  + 可选：session_context hooks（若 hooks 输出不稳定，Phase 1 先移出或固定）

[禁止再出现]
  modify / todo plan / datasets catalog / deliverables / loaded names / filter_context
```

### 本轮 user 组装（扩展既有 scope 通道）

```
compose_llm_user_content(teacher_text, turn_hint)
turn_hint = join_nonempty(
  format_turn_scope_hint(...),          # 已有
  format_modify_turn_hint(...),         # 新：原 system modify 段
  format_todo_turn_hint(...),           # 新：当前计划摘要（可选短）
  format_report_continue_hint(...),     # 新：原 inject 回写逻辑改为返回字符串
  optional_first_turn_catalog_hint(...),# 可选：空会话首轮 datasets 快照
)
```

HTTP `service._execute_turn` 与 eval `runner` 必须走同一组装函数，避免双路径漂移。

---

## File Map

| 文件 | 职责 |
|------|------|
| `backend/agent/common/system_prompt.py` | 砍掉 volatile 段；稳定 system |
| `backend/agent/common/prompts.py` | 保留 format_*；新增/调整 turn-hint 文案；MEMORY_GUIDANCE 并入 base 或固定顺序 |
| `backend/agent/session/ui_scope.py` 或新建 `session/turn_hints.py` | 统一本轮 hint 组装（推荐新建以免 ui_scope 过肥） |
| `backend/agent/http/service.py` | 组装 turn_hint（modify/todo/reminder），禁止回写 |
| `backend/agent/eval/runner.py` | 与 HTTP 同路径注入 |
| `backend/agent/loop.py` | `_system_prompt` 瘦身；reminder 改为 hint；micro_compact 策略 |
| `backend/agent/hints/report_continue.py` | 改为纯函数返回 hint，不 mutate messages |
| `backend/agent/context/micro_compact.py` | cache-safe 边界 + bust 日志 |
| `backend/agent/tools/handlers/todo_write.py` / data postprocess / deliverables | B：result 附快照 |
| `backend/agent/test/test_*.py` | 前缀稳定性、不回写、hint 组装 |
| `backend/agent/eval/metrics/cost.py`（可选） | 记录 median cache ratio，非硬门禁 |

---

### Task 1: 回归锚点 — system 前缀稳定性测试

**Files:**
- Create: `backend/agent/test/test_prompt_cache_stability.py`
- Modify: （无，先红）

**Interfaces:**
- Consumes: `SystemPromptBuilder.build`, `SystemPromptContext`
- Produces: 失败测试定义「同 mode 下动态字段变化不得改变 system 字符串」的契约（实现后变绿）

- [ ] **Step 1: Write the failing test**

```python
# backend/agent/test/test_prompt_cache_stability.py
from common.system_prompt import SystemPromptBuilder, SystemPromptContext


def test_system_prompt_stable_across_volatile_session_state():
    b = SystemPromptBuilder()
    base = b.build(SystemPromptContext(permission_mode="analyze"))
    volatile = b.build(
        SystemPromptContext(
            permission_mode="analyze",
            todo_items=[{"content": "q", "status": "in_progress"}],
            loaded_skills={"data-exploration"},
            modify_context={"parent_run_id": "r1", "strategy": "requery", "patch": {}},
            session_id="sess-cache-test",  # even if datasets exist, must not enter system
        )
    )
    assert base == volatile, (
        "system must be byte-stable within mode; put volatile state in turn user / tool results"
    )


def test_system_prompt_may_differ_across_modes():
    b = SystemPromptBuilder()
    a = b.build(SystemPromptContext(permission_mode="analyze"))
    p = b.build(SystemPromptContext(permission_mode="produce"))
    assert a != p
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend/agent && py -3.11 -m pytest test/test_prompt_cache_stability.py -v`  
Expected: FAIL — `base == volatile` 失败（当前 system 含 todo/modify/loaded）

- [ ] **Step 3: （本 Task 不实现生产代码；仅确认红灯）**

- [ ] **Step 4: 暂存，待用户要求再 commit**

---

### Task 2: 冻结 system — 移出 todo / datasets / deliverables / modify / loaded names

**Files:**
- Modify: `backend/agent/common/system_prompt.py`
- Modify: `backend/agent/common/prompts.py`（`build_base_agent_prompt` 末尾并入 `MEMORY_GUIDANCE` 或 build 时固定在 permission 之后、任何动态段之前——最终动态段应为空）
- Modify: `backend/agent/test/test_scope_summary.py`（datasets 不再要求出现在 system）
- Modify: `backend/agent/test/test_system_prompt.py`（更新断言）
- Test: `backend/agent/test/test_prompt_cache_stability.py`（应变绿）

**Interfaces:**
- Consumes: Task 1 契约
- Produces: `SystemPromptBuilder.build` 在同 mode 下忽略 `todo_items` / `modify_context` / `session_id` catalogs / `loaded_*`（字段可保留但未使用，或标 deprecated）

- [ ] **Step 1: 改 `SystemPromptBuilder.build`，删除/跳过以下 append**

从 `system_prompt.py` 的 `build()` 去掉：

- `format_run_modify_section`
- `format_datasets_catalog_section` / `_format_datasets_catalog_prompt`
- `format_loaded_skill_names_section`（含 produce 自动加 report-writing 名单）
- `format_session_plan_section`
- `format_session_deliverables_section`

保留：`build_base_agent_prompt`、memory index（本阶段可留）、`format_permission_mode`、`format_session_section`（hooks）、`format_skills_section`、`MEMORY_GUIDANCE`。

将 `MEMORY_GUIDANCE` 紧接在静态 base + permission 之后，避免「插段位移」。

- [ ] **Step 2: 更新旧测试**

- `test_system_prompt_omits_dynamic_filter_scope`：保持。
- `test_format_datasets_catalog_section_and_prompt`：仍测 `format_datasets_catalog_section` 辅助函数，但 **不再** assert catalog 出现在 `SystemPromptBuilder.build` 结果中；改为 assert **不在** system。
- 任何依赖 system 含 todo/loaded 的测试改为测 turn hint / tool result。

- [ ] **Step 3: Run tests**

Run:

```bash
cd backend/agent
py -3.11 -m pytest test/test_prompt_cache_stability.py test/test_system_prompt.py test/test_scope_summary.py -q
```

Expected: Task 1 稳定性测试 PASS；相关旧测试 PASS 或已按新契约改写。

---

### Task 3: 本轮 hint 通道（策略 A）— modify / todo / report reminder

**Files:**
- Create: `backend/agent/session/turn_hints.py`
- Modify: `backend/agent/session/ui_scope.py`（可选：`compose_llm_user_content` 保持；hint 拼接放到 `turn_hints`）
- Modify: `backend/agent/hints/report_continue.py`
- Modify: `backend/agent/http/service.py`（`_execute_turn`）
- Modify: `backend/agent/eval/runner.py`
- Modify: `backend/agent/loop.py`（停止调用 mutating `inject_report_continue_reminder`）
- Test: `backend/agent/test/test_turn_hints.py`（新建）、`backend/agent/test/test_ui_scope.py`、`backend/agent/test/test_report_continue.py`

**Interfaces:**
- Produces:

```python
def build_turn_agent_hint(
    *,
    ui_scope: dict | None = None,
    filter_context: FilterContext | None = None,
    modify_context: dict | None = None,
    todo_items: list[dict[str, str]] | None = None,
    report_continue_path: str | None = None,
    datasets_catalog_text: str | None = None,  # 仅首轮可选
) -> str | None: ...

def format_report_continue_hint(path: str) -> str: ...  # 纯函数，无副作用
```

- [ ] **Step 1: Write failing tests**

```python
def test_build_turn_hint_includes_modify_and_does_not_mutate_history():
    messages = [{"role": "user", "content": "旧问题"}]
    hint = build_turn_agent_hint(
        modify_context={"parent_run_id": "r1", "strategy": "requery", "patch": {}},
        todo_items=[{"content": "query", "status": "in_progress"}],
    )
    assert hint and "r1" in hint and "query" in hint
    assert messages[0]["content"] == "旧问题"


def test_report_continue_is_hint_not_rewrite():
    from hints.report_continue import format_report_continue_hint
    # inject_report_continue_reminder must not rewrite; prefer format_* + compose
    msgs = [{"role": "user", "content": "继续写报告"}]
    hint = format_report_continue_hint("reports/class/Class1/overview.md")
    assert "reports/class/Class1/overview.md" in hint
    assert msgs[0]["content"] == "继续写报告"
```

- [ ] **Step 2: Implement `turn_hints.py`**

复用 `format_run_modify_section` / 精简版 todo 渲染（可抽 `format_session_plan_section` 的短版，限制 ≤N 行）。  
`compose_llm_user_content(teacher, build_turn_agent_hint(...))` 在 HTTP 与 eval runner 各一处调用。

- [ ] **Step 3: 改掉 `inject_report_continue_reminder`**

- 保留路径探测 `latest_report_path`。
- 删除对 `messages[idx] = {..., content: old+reminder}` 的回写。
- `loop._run_turn_body` 不再调用 mutating inject；reminder 只在 **开启该用户 turn 时** 由 HTTP/eval 拼进本轮 user。

- [ ] **Step 4: Run tests**

```bash
py -3.11 -m pytest test/test_turn_hints.py test/test_ui_scope.py test/test_report_continue.py test/test_prompt_cache_stability.py -q
```

Expected: PASS

---

### Task 4: 策略 B — datasets / deliverables / todo 快照进 tool result

**Files:**
- Modify: `backend/agent/tools/handlers/todo_write.py`（result 末尾附当前计划渲染）
- Modify: `backend/agent/tools/runtime/pipeline/postprocess.py` 或 data tool 成功路径（query/aggregate 注册 dataset 后附 `format_catalog_hint` 短尾）
- Modify: deliverable 记录点（`record_deliverable_from_tool` 调用后追加列表快照到该 tool result）
- Test: `backend/agent/test/test_session_tools_batch3.py`、`test_list_datasets.py`、`test_deliverables_registry.py`（扩展）

**Interfaces:**
- Produces: tool result 字符串约定后缀，例如：

```text
---
[session_snapshot]
datasets: ...
plan: ...
deliverables: ...
```

- [ ] **Step 1: Write failing tests** — `todo_write` 成功输出含计划摘要；dataset append 后相关 tool result 含 `dataset_id=`。

- [ ] **Step 2: 最小实现** — 复用 `format_session_plan_section` / `format_catalog_hint` / `format_deliverables_prompt`，截断 tail（datasets 8、deliverables 5）。

- [ ] **Step 3: 首轮可选 A** — 若 session 已有 datasets 且本轮是该 session 第一条 user，可在 `build_turn_agent_hint` 注入一次 catalog（避免「从未 list 就不知道 id」）；**之后不再每轮重复塞满 catalog**（靠 B）。

- [ ] **Step 4: pytest 相关文件 PASS**

---

### Task 5: micro_compact cache-safe

**Files:**
- Modify: `backend/agent/context/micro_compact.py`
- Modify: `backend/agent/context/config.py`（可选：`micro_compact_cache_mode: literal["tail_only","bust_ok"]`）
- Modify: `backend/agent/loop.py`（传入「上一请求已缓存消息前缀长度」或 `protected_prefix_count`）
- Test: `backend/agent/test/test_context_compact.py`

**Interfaces:**
- Produces:

```python
def micro_compact_messages(
    messages: list[dict[str, Any]],
    *,
    config: ContextCompactConfig = DEFAULT_CONFIG,
    protect_prefix_count: int | None = None,
    on_cache_bust: Callable[[str], None] | None = None,
) -> int: ...
```

**策略（混合，默认）：**

1. 若 `protect_prefix_count` 有值：只允许 compact index `>= protect_prefix_count` 的 tool 消息（尾部未缓存区）。
2. 若必须 compact 保护区内消息才能腾空间：执行 compact，并 `on_cache_bust("micro_compact")` / `log_event(..., cache_bust_reason="micro_compact")`。
3. **调用时机**：仍可在 `_apply_pre_turn_compaction`；但 `protect_prefix_count` = 上一轮 LLM 请求时的 `len(messages)`（在请求前快照）。首轮 user turn 无保护。

- [ ] **Step 1: 失败测试** — 给定 5 条 tool，`protect_prefix_count=4` 时前 3 条正文不变。

- [ ] **Step 2: 实现 + 打日志**

- [ ] **Step 3: pytest `test_context_compact.py` PASS**

---

### Task 6: 观测与 benchmark 验收

**Files:**
- Modify: `backend/agent/eval/metrics/cost.py`（可选 evidence 字段保持）
- Modify: `docs/eval/agent-benchmark.md` 短节：如何读 `median_cached_tokens` / ratio
- Run: 小规模 live 或 dry 对照（用户环境有 key 时）

**验收标准（非硬门禁）：**

1. 同 session、同 mode、连续 tool round：**system 字符串哈希不变**（单测已锁）。
2. 手工/脚本：第二+ 次 LLM call 的 `cached_tokens / input_tokens` 相对改前提升（对照 `data/eval/runs/*` 中 scope 场景 ~30–55%；目标看趋势而非一次数字）。
3. 正确性：既有 `test_ui_scope` / binding 相关单测不回退；可选 `--runs 1` smoke scope 场景。

- [ ] **Step 1: 增加调试日志**（debug）：每轮 LLM 前 `system_sha256[:12]`，变化时 warn。

- [ ] **Step 2: 跑稳定性单测全集**

```bash
cd backend/agent
py -3.11 -m pytest test/test_prompt_cache_stability.py test/test_turn_hints.py test/test_ui_scope.py test/test_context_compact.py test/test_system_prompt.py -q
```

- [ ] **Step 3: （可选）live cache probe** `scripts/run_langfuse_cache_live.py` 确认仍能读到 cache hit。

---

## 实施顺序与依赖

```text
Task1 (红灯契约)
  → Task2 (冻 system)
  → Task3 (A: turn hints + 修 reminder)
  → Task4 (B: tool snapshots)
  → Task5 (micro_compact)
  → Task6 (观测验收)
```

Task3 与 Task4 可部分并行，但 Task3 应先于「依赖本轮 modify 提示」的行为回归。

## 明确非目标（本计划不做）

- Anthropic `cache_control` 双 content block。
- 重做持久 memory 系统或 Dream consolidator。
- 把 `cache_hit_rate` 改成硬门禁（仍为 P2 效率指标）。
- 为省 cache 而关闭 micro/macro compact。

## Spec coverage（自检）

| 调研要点 | 对应 Task |
|----------|-----------|
| todo/datasets/deliverables/modify 移出 system | Task 2–4 |
| A 本轮 user / B tool result，禁止回写 | Task 3–4 Global Constraints |
| micro_compact 尾部优先 + bust 日志 | Task 5 |
| report reminder 尾部/本轮 user | Task 3 |
| 不影响已缓存前缀 | Task 1 契约 + Task 5–6 |

## 风险

- Agent 可能暂时「看不到」仅存在于旧 system 的 datasets/todo → 用 Task4 快照 + 首轮 A 缓解；必要时工具描述里写「用 list_datasets / 看上一次 tool 快照」。
- produce 自动 pin `report-writing` 仍靠 messages bootstrap（已是 append），不依赖 system loaded 名单。
