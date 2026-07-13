"""
All agent LLM prompt text: static templates and format helpers.

NorthClassVision — 面向教师的学业数据分析 Agent。动态数据由调用方注入；
本模块只维护措辞与分区结构。
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# System prompt — layered static body (mode-specific via build_base_agent_prompt)
# ---------------------------------------------------------------------------

_AGENT_INTRO = """你是 **NorthClassVision** 的教师辅助数据分析 Agent，帮助教师探索学业数据、形成分析结论，并（在允许时）撰写可交付的报告。"""

_WORKSPACE = """## 工作区
- 数据根目录：`data/`（工具路径均相对此根，勿写盘符绝对路径）
- 原始学业 CSV（`Data_StudentInfo.csv`、`Data_TitleInfo.csv`、`Data_SubmitRecord/*.csv`）**只读**，禁止改写
- 分析交付物写入 `reports/` 或 `exports/`
- 元数据：`meta/data_catalog.md`（Session 有索引；全文在 analyze/produce 下可 `read_file` 读 `meta/`）"""

_DATA_CORE = """## 学业数据（逻辑 resource）
- 注册表：`meta/resource_registry.yaml`；字段与样例用 `inspect_schema`
- **禁止** `read_file` 打开上述原始 CSV；结构化分析用 `inspect_schema` → `query_data` → `aggregate_data`
- 常用 resource：`student_info`、`title_info`、`submit_record`（需 `class` 或 `classes`）、`week_aggregation`
- 关联键：`student_ID`、`title_ID`、`class`、`major`
- Nav「当前分析范围」每轮同步 scope（**用户消息 / query 参数优先**；与面板班级或选区冲突时自动忽略面板局部选中；完整学号用 `get_current_filter_context(include_student_ids=true)`）"""

_DATA_DECISIONS = """## 常用决策（IF → THEN）
| 目标 | 做法 |
|------|------|
| 统计人数 | `aggregate_data` + `count_distinct` + `field=student_ID`（`count` 仅为提交行数） |
| 全量统计 | `query_data` **省略** `limit`；禁止 `limit:0` |
| 聚合 | 先 `query_data`，再 `aggregate_data` 且 `input={"result_ref": "<meta.result_ref>"}` |
| 专业过滤 | `submit_record` 传 `majors` 或 `where` 字段 `major`（勿把专业码写入 `student_ID`） |
| 选中学生 | 教师说「我选的」→ 用 Nav 选区；**班级总览/消息中指定 ClassN** → `query_data` 用该班，**忽略**面板错位选区 |
| 图表跳转 | 结论后用 `build_visual_links`（勿手写未校验的 view 名） |
| 多步任务 | `todo_write` 含 `acceptance`；`meta.warnings` 未清勿标 completed |"""

_MODE_EXTENSIONS: dict[str, str] = {
    "consult": """## 本模式能力（consult）
- **可用**：`inspect_schema`、`list_files`、`load_skill`、`get_current_filter_context`
- **不可用**：`read_file`、`query_data`、`aggregate_data`、`build_visual_links`
- 需要计数、均值、图表跳转或读 `meta/`/`reports/` → 请教师切换到 **analyze**；要写交付报告 → **produce**""",
    "analyze": """## 本模式能力（analyze）
- **在 consult 基础上增加**：`query_data`、`aggregate_data`、`build_visual_links`
- **`read_file` 仅** `meta/`（契约与 catalog）；**禁止**读 `reports/`、`exports/` 下已有产出物
- 流程：`inspect_schema` → `query_data` → `aggregate_data`；向教师给出结论后 `build_visual_links`""",
    "produce": """## 本模式能力（produce）
- **在 analyze 基础上**：可**写入** `reports/`（所有 Markdown 报告）；`exports/` 仅非报告导出
- **报告写作规范**：produce 下 `report-writing` 自动登记；正文在 load_skill 的 tool result（勿重复 load）
- **标准**个体/班级/专业总览：按需 `load_reference` 对应 tier 参考（如 student/class/major）
- **修订通读**：全部章节写完后用 `review_report` 做跨节一致性检查（返回 issues，非全文）
- **通用**报告（窄窗、备忘、对比）：仅遵守 `report-writing`，路径如 `reports/notes/<主题>.md`；勿硬套 analysis-*""",
}

_WORKFLOW = """## 工作方式
- **调用工具前**：同一轮 assistant 回复里先用 2–4 句中文说明理解、范围与下一步，再 `tool_calls`（纯闲聊可例外）
- **三轮叙事（UI 三段）**：计划段（第一次 tool 前，只写步骤、禁止数字结论）→ 过程段（每轮 tool 前 1–2 句过渡）→ 结论段（最后一轮无 tool，写完整分析）
- 固定流程用 `load_skill`（首次加载后 SKILL 全文在 tool result，会话内 pin 不压缩）；计划见「当前执行计划」（与 `todo_write` 同步）
- 对话过长用 `compact` 或自动压缩，继续当前分析目标
- 回答用清晰中文，结论有数据依据；不确定时说明局限与下一步（换班、读 catalog、切换模式等）"""

_LOAD_SKILL_TABLE = """## 何时 load_skill

| 教师意图 / 粒度 | 优先 load |
|-----------------|-----------|
| 个体、点名、变差、诊断 | `load_reference("student")` |
| 本班、ClassN、班级整体 | `load_reference("class")` |
| 专业、跨班 | `load_reference("major")` |
| 不知 resource / 字段、纯探查 | `data-exploration` |
| 写报告（produce） | `report-writing`（produce 自动登记）；标准诊断/总览再按需 `load_reference` |
| 报告修订（produce） | 章节写完后 `review_report` → 按 fix `edit_file` ## 整节替换 |
| 长报告流水线（analyze/produce） | `run_subagent(data_analyst)` → 父 Agent 整合 → `run_subagent(report_writer)` → 可选 `report_reviewer` |
| analyze 中向教师展示图 | `build_visual_links`（与后续 report-chart params 一致） |

规划约束见 `meta/analysis_ontology.yaml`。所有报告写入 `reports/`；禁止 read 参考旧稿。"""


def build_base_agent_prompt(mode: str = "consult") -> str:
    """Assemble mode-sliced static system prompt body."""
    key = (mode or "consult").strip().lower()
    mode_block = _MODE_EXTENSIONS.get(key, _MODE_EXTENSIONS["consult"])
    return "\n\n".join(
        [
            _AGENT_INTRO,
            _WORKSPACE,
            _DATA_CORE,
            _DATA_DECISIONS,
            mode_block,
            _WORKFLOW,
            _LOAD_SKILL_TABLE,
        ]
    )


# Legacy alias (analyze-sized body); tests and callers should prefer build_base_agent_prompt(mode).
BASE_AGENT_PROMPT = build_base_agent_prompt("analyze")

MEMORY_GUIDANCE = """**memory / save_memory**（跨会话持久记忆，analyze/produce）：仅保存教师**长期**偏好、纠正、项目约定；须教师明确说「记住」或纠正写法后再存。target=user（偏好）| memory（流程约定）；save_memory 用于具名主题。**禁止**写入：学号/周次/单次报告状态、reports/ 路径、统计结论、本轮 TODO、密钥——这些属于**本会话**（todo_write、已写 reports/ 交付物列表）或报告文件。"""

# ---------------------------------------------------------------------------
# System prompt — section titles & templates
# ---------------------------------------------------------------------------

SECTION_MEMORY_TITLE = "# 持久记忆（跨会话）"
SECTION_MEMORY_TYPE = "## [{mem_type}]"
SECTION_MEMORY_ENTRY = "### {name}：{description}"

SECTION_SESSION = "--- 会话上下文（Hooks / 数据目录摘要）---"
SECTION_UI_SCOPE = "--- 当前分析范围（可视化面板 / Nav，每轮 HTTP 同步）---"
SECTION_SKILLS = "--- 可用技能（目录；完整流程见 load_skill 的 tool result）---"
SECTION_LOADED_NAMES = "--- 本会话已加载（正文在对应 tool result，勿重复 load）---"
SECTION_LOADED_SKILLS = SECTION_LOADED_NAMES  # legacy alias
SECTION_LOADED_REFERENCES = SECTION_LOADED_NAMES  # legacy alias
SECTION_SESSION_PLAN = "--- 当前执行计划（与 todo_write / 右栏同步，每轮注入）---"
SECTION_SESSION_DELIVERABLES = "--- 本会话交付物（write_file 到 reports/exports，非跨会话记忆）---"

LOADED_SKILL_BODY_PROMPT_MAX_CHARS = 12_000

PERMISSION_MODE_TEMPLATE = """当前能力模式：**{mode}**
{mode_hint}
若工具被拒绝，向教师说明模式限制，并给出可执行替代（如切 analyze 查数、切 produce 写报告）。"""

MODE_CAPABILITY_HINTS: dict[str, str] = {
    "consult": (
        "探查：仅 schema / 列文件 / 技能 / 当前 scope。"
        "无 read_file、query_data、build_visual_links。"
        "Nav scope 摘要见「当前分析范围」；需学号列表时 get_current_filter_context(include_student_ids=true)。"
        "说明切 analyze 可查询表现。"
    ),
    "analyze": (
        "分析：query_data + aggregate_data + build_visual_links；"
        "全量省略 limit；人数用 count_distinct(student_ID)；"
        "aggregate 用 result_ref；dataset_id 不明时用 list_datasets。"
    ),
    "produce": (
        "交付：report-writing 已注入；标准总览/诊断再加 analysis-*；"
        "一律 write 到 reports/；按叙述意图嵌 report-chart；勿 read 旧 reports。"
    ),
}

# ---------------------------------------------------------------------------
# Context compaction (macro / micro)
# ---------------------------------------------------------------------------

COMPACT_SUMMARY_SYSTEM = (
    "你负责压缩 NorthClassVision 教师学业数据分析对话的上下文，"
    "保留继续分析所需的关键信息，表述简练但具体。"
)

COMPACT_SUMMARY_USER_TEMPLATE = """请压缩以下 NorthClassVision 学业数据分析对话，便于 Agent 在更短的上下文中继续工作。

务必保留：
1. 教师的分析目标（班级、知识点、对比维度等）
2. 已确认的数据发现、统计结论与重要决策
3. 已读取或写入的文件路径（meta/、reports/、exports/ 等，勿依赖已读的原始 CSV）
4. 尚未完成的步骤（含 todo 各条 content、status、acceptance）
5. 已加载的技能/参考名称及须遵守的流程要点（非 SKILL 全文；正文在 pin 的 tool result）
6. 教师约束与偏好（格式、范围、注意事项）
7. **学业数据仅经 resource 工具（inspect_schema / query_data），禁止 read_file 原始 Data_*.csv**

对话记录（JSON）：
{conversation}
"""

COMPACT_SUMMARY_FALLBACK = "（摘要生成失败；请结合最近工具结果与 Session 中的数据目录摘要继续分析。）"

COMPACT_USER_MESSAGE_PREAMBLE = (
    "以下内容为对话压缩摘要，请在此基础上继续 NorthClassVision 学业数据分析。"
)

COMPACT_FOCUS_SUFFIX = "\n\n下一轮请优先保留：{focus}"

COMPACT_RECENT_FILES_SUFFIX = "\n\n近期涉及的文件（必要时可重新打开）：\n{files}"

OUTPUT_CONTINUATION_MESSAGE = (
    "输出已达到长度上限。请从上次中断处直接继续，不要复述、不要总结前文；"
    "若句子未写完，从中途接着写即可。"
)


# ---------------------------------------------------------------------------
# Format helpers (dynamic sections)
# ---------------------------------------------------------------------------

def format_permission_mode(mode: str) -> str:
    hint = MODE_CAPABILITY_HINTS.get(
        mode.lower(),
        "请遵守当前模式下的工具权限。",
    )
    return PERMISSION_MODE_TEMPLATE.format(mode=mode, mode_hint=hint).strip()


def format_run_modify_section(modify_context: dict[str, Any] | None) -> str:
    """System-prompt section for derive/modify turns (not shown in UI)."""
    if not modify_context:
        return ""
    import json

    preview = {
        k: modify_context.get(k)
        for k in (
            "parent_run_id",
            "parent_tool",
            "strategy",
            "patch",
            "source",
            "parent_dataset_id",
            "parent_result_ref",
        )
        if modify_context.get(k) is not None
    }
    parent_params = modify_context.get("parent_params") or {}
    if isinstance(parent_params, dict):
        preview["parent_params_preview"] = {
            k: parent_params.get(k)
            for k in ("resource", "class", "classes", "group_by", "where", "limit")
            if parent_params.get(k) is not None
        }
    body = json.dumps(preview, ensure_ascii=False, default=str)
    strategy = modify_context.get("strategy")
    if strategy in ("reaggregate", "reuse_aggregate"):
        instruction = (
            "**强制**：本 turn 禁止调用 query_data。"
            "系统已在首轮自动执行 aggregate_data；若需调整请仅改 metrics / dimensions。"
            "input 含 parent_dataset_id / parent_result_ref（已自动注入）。"
        )
    elif strategy == "requery":
        instruction = (
            "**强制**：本 turn 使用 query_data 并继承 parent 未改条件，仅应用 patch。"
            "完成后如需指标再 aggregate_data。"
        )
    else:
        instruction = "请继承 parent 未改条件，仅应用 patch；避免不必要的全量重查。"
    return (
        "## 本轮：数据计算修改（系统内部，勿复述给用户）\n"
        f"{body}\n"
        f"{instruction}"
    )


def format_session_section(blocks: list[str]) -> str:
    """Join hook-injected session blocks under the session section header."""
    body = "\n\n".join(b for b in blocks if b and b.strip())
    return f"{SECTION_SESSION}\n{body}"


def format_filter_context_section(scope: dict) -> str:
    """Human-readable Nav scope summary for the system prompt (no bulky ID lists)."""
    lines = [SECTION_UI_SCOPE]
    classes = scope.get("classes") or []
    majors = scope.get("majors") or []
    week_range = scope.get("week_range")
    count = scope.get("selected_student_count")
    if count is None:
        legacy = scope.get("selected_student_ids") or []
        count = len(legacy) if legacy else 0
    preview = scope.get("selected_student_ids_preview") or []

    if classes:
        lines.append(f"- 班级 classes: {', '.join(str(c) for c in classes)}")
    if majors:
        major_preview = ", ".join(str(m) for m in majors[:8])
        if len(majors) > 8:
            major_preview = f"{major_preview} …（共 {len(majors)} 个）"
        lines.append(f"- 专业 majors: {major_preview}")
    if week_range is not None and len(week_range) == 2:
        lines.append(f"- 周次 week_range: {week_range[0]}–{week_range[1]}")

    if count and count > 0:
        lines.append(f"- 已选学生: **{count} 人**（Nav 选区已绑定会话，`query_data` 自动应用）")
        if count <= 3 and preview:
            lines.append(f"  - ID: {', '.join(str(s) for s in preview)}")
        lines.append(
            "  - 教师说「我选的 / 选中的」→ 直接用 Nav 选区，勿索要学号；"
            "需完整列表 → `get_current_filter_context(include_student_ids=true)`。"
        )
    else:
        lines.append("- 已选学生: （散点图未选中）")
        typical = scope.get("typical_student_ids") or []
        if typical:
            lines.append(
                f"- WeekView 代表学生 typical_student_ids: {', '.join(str(s) for s in typical)}"
            )
            lines.append(
                "  - build_visual_links / report-chart 必须使用以上真实学号，禁止 student1 等占位符。"
            )

    lines.append(
        "- **范围优先级**：教师消息或 `query_data` 中的 class/classes 优先于面板；"
        "班级总览且未说「我选的」时，自动忽略与查询班级不一致的面板选区。"
    )

    return "\n".join(lines)


def format_skills_section(catalog: str) -> str:
    """Wrap skill registry catalog text."""
    return f"{SECTION_SKILLS}\n{catalog.strip()}"


def format_loaded_skill_names_section(
    loaded_skills: list[str] | set[str] | None = None,
    loaded_references: list[str] | set[str] | None = None,
) -> str:
    """Lightweight list of loaded skill/reference ids (bodies live in tool results)."""
    skills = sorted({str(n).strip() for n in (loaded_skills or []) if str(n).strip()})
    refs = sorted({str(n).strip() for n in (loaded_references or []) if str(n).strip()})
    if not skills and not refs:
        return ""
    lines = [SECTION_LOADED_NAMES]
    if skills:
        lines.append(f"- skills: {', '.join(skills)}")
    if refs:
        lines.append(f"- references: {', '.join(refs)}")
    return "\n".join(lines)


def format_loaded_skills_section(
    registry: Any,
    loaded_names: list[str] | set[str],
    *,
    max_chars_per_skill: int = LOADED_SKILL_BODY_PROMPT_MAX_CHARS,
) -> str:
    """Deprecated: full bodies in tool results. Kept for tests importing the name."""
    _ = registry, max_chars_per_skill
    return format_loaded_skill_names_section(loaded_skills=loaded_names)


def format_loaded_references_section(
    loaded_names: list[str] | set[str],
    *,
    max_chars_per_ref: int = LOADED_SKILL_BODY_PROMPT_MAX_CHARS,
) -> str:
    _ = max_chars_per_ref
    return format_loaded_skill_names_section(loaded_references=loaded_names)


def format_session_plan_section(items: list[dict[str, str]]) -> str:
    """Render todo_write plan for system prompt (mirrors TodoManager.render)."""
    if not items:
        return ""
    lines = [SECTION_SESSION_PLAN]
    for raw in items:
        content = str(raw.get("content", "")).strip()
        if not content:
            continue
        status = str(raw.get("status", "pending")).lower()
        marker = {"pending": "[ ]", "in_progress": "[>]", "completed": "[√]"}.get(
            status, "[ ]"
        )
        line = f"{marker} {content}"
        active = str(raw.get("active_form", "")).strip()
        if status == "in_progress" and active:
            line += f" ({active})"
        acceptance = str(raw.get("acceptance", "")).strip()
        if acceptance:
            line += f"\n    Acceptance: {acceptance}"
        lines.append(line)
    completed = sum(
        1 for raw in items if str(raw.get("status", "")).lower() == "completed"
    )
    lines.append(f"Completed: {completed}/{len(items)}")
    lines.append(
        "更新计划请用 todo_write；本节每轮自动同步，勿依赖已被压缩的旧 tool 消息。"
    )
    return "\n".join(lines)


def format_session_deliverables_section(block: str) -> str:
    text = (block or "").strip()
    if not text:
        return ""
    return f"{SECTION_SESSION_DELIVERABLES}\n{text}"


def format_memory_type_header(mem_type: str) -> str:
    return SECTION_MEMORY_TYPE.format(mem_type=mem_type)


def format_memory_entry_header(name: str, description: str) -> str:
    return SECTION_MEMORY_ENTRY.format(name=name, description=description)


def format_compact_summary_user(conversation_json: str) -> str:
    return COMPACT_SUMMARY_USER_TEMPLATE.format(conversation=conversation_json)


def format_compact_user_message(
    summary: str,
    *,
    focus: str | None = None,
    recent_files: list[str] | None = None,
) -> str:
    """User-role message injected after macro compaction."""
    body = summary.strip()
    if focus:
        body += COMPACT_FOCUS_SUFFIX.format(focus=focus)
    if recent_files:
        lines = "\n".join(f"- {path}" for path in recent_files)
        body += COMPACT_RECENT_FILES_SUFFIX.format(files=lines)
    return f"{COMPACT_USER_MESSAGE_PREAMBLE}\n\n{body}"
