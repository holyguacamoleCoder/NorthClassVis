# 系统提示词与输出格式约束，供编排层调用 LLM 时使用。

import json


SYSTEM_PROMPT = """你是教师学情分析助手。

你的首要原则：
1. 只能基于真实 observation 回答，不得编造学生、题目、知识点、班级、专业或统计结果。
2. 先判断问题想要的分析粒度，再决定是否继续取数；不要为了“看起来努力”而盲目调工具。
3. 如果问题要求特定范围（如某班级、某专业、某学生、某知识点），回答必须优先围绕该范围；不能偷偷退化成“全班整体”却不说明。
4. 如果现有工具或 observation 无法支撑该粒度，必须明确指出“当前数据不足以支持该结论”，并说明缺的是什么维度。
5. 结论保持简短、可验证，建议使用“可关注”“建议”“可优先”等措辞，避免绝对化判断。
"""

OUTPUT_FORMAT_INSTRUCTION = """请按以下 JSON 结构输出（仅输出 JSON，不要其他说明）：
{"answer": "1～3 句结论摘要", "actions": ["建议一", "建议二"]}
"""


INTENT_FEW_SHOTS = [
    {"role": "user", "content": "这周班里整体趋势怎么样？"},
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "intent_type": "trend",
                "subject": ["class"],
                "mode": ["trend"],
                "scope": "all",
                "metric": "weekly_score",
                "knowledge": None,
                "title_id": None,
                "student_ids": [],
                "classes": [],
                "majors": [],
                "time_window": "recent_2w",
                "needs_clarification": False,
                "clarification_question": "",
                "is_out_of_domain": False,
            },
            ensure_ascii=False,
        ),
    },
    {"role": "user", "content": "链表这个知识点难在哪里？"},
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "intent_type": "knowledge",
                "subject": ["knowledge"],
                "mode": ["portrait"],
                "scope": "all",
                "metric": "knowledge_score",
                "knowledge": "链表",
                "title_id": None,
                "student_ids": [],
                "classes": [],
                "majors": [],
                "time_window": "",
                "needs_clarification": False,
                "clarification_question": "",
                "is_out_of_domain": False,
            },
            ensure_ascii=False,
        ),
    },
    {"role": "user", "content": "帮我看看这个学生最近学得怎么样"},
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "intent_type": "student",
                "subject": ["student"],
                "mode": ["portrait"],
                "scope": "all",
                "metric": "student_profile",
                "knowledge": None,
                "title_id": None,
                "student_ids": [],
                "classes": [],
                "majors": [],
                "time_window": "",
                "needs_clarification": True,
                "clarification_question": "请说明您想分析哪位学生，或先在界面框选学生。",
                "is_out_of_domain": False,
            },
            ensure_ascii=False,
        ),
    },
    {"role": "user", "content": "第5题大家答对率的时间变化"},
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "intent_type": "question",
                "subject": ["question"],
                "mode": ["detail"],
                "scope": "individual",
                "metric": "",
                "knowledge": None,
                "title_id": "5",
                "student_ids": [],
                "classes": [],
                "majors": [],
                "time_window": "",
                "needs_clarification": False,
                "clarification_question": "",
                "is_out_of_domain": False,
            },
            ensure_ascii=False,
        ),
    },
    {"role": "user", "content": "班里的学生分层是什么情况？"},
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "intent_type": "cluster",
                "subject": ["class"],
                "mode": ["cluster"],
                "scope": "all",
                "metric": "cluster_distribution",
                "knowledge": None,
                "title_id": None,
                "student_ids": [],
                "classes": [],
                "majors": [],
                "time_window": "",
                "needs_clarification": False,
                "clarification_question": "",
                "is_out_of_domain": False,
            },
            ensure_ascii=False,
        ),
    },
    {"role": "user", "content": "给我看看 s001 的学习路径和提交明细"},
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "intent_type": "submission",
                "subject": ["student"],
                "mode": ["detail"],
                "scope": "individual",
                "metric": "submission_count",
                "knowledge": None,
                "title_id": None,
                "student_ids": ["s001"],
                "classes": [],
                "majors": [],
                "time_window": "",
                "needs_clarification": False,
                "clarification_question": "",
                "is_out_of_domain": False,
            },
            ensure_ascii=False,
        ),
    },
    {"role": "user", "content": "看看这两个学生最近趋势和画像"},
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "intent_type": "student",
                "subject": ["student"],
                "mode": ["trend", "portrait"],
                "scope": "selected",
                "metric": "student_profile",
                "knowledge": None,
                "title_id": None,
                "student_ids": ["s001", "s002"],
                "classes": [],
                "majors": [],
                "time_window": "recent_2w",
                "needs_clarification": False,
                "clarification_question": "",
                "is_out_of_domain": False,
            },
            ensure_ascii=False,
        ),
    },
    {"role": "user", "content": "看看 s001 的最近趋势，还有链表知识点掌握情况"},
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "intent_type": "trend",
                "subject": ["student", "knowledge"],
                "mode": ["trend", "portrait"],
                "scope": "individual",
                "metric": "weekly_score",
                "knowledge": "链表",
                "title_id": None,
                "student_ids": ["s001"],
                "classes": [],
                "majors": [],
                "time_window": "recent_2w",
                "needs_clarification": False,
                "clarification_question": "",
                "is_out_of_domain": False,
            },
            ensure_ascii=False,
        ),
    },
    {"role": "user", "content": "先看下全班最近两周的整体趋势，再帮我看看张三和李四这两个学生的画像。"},
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "intent_type": "overview",
                "sub_goals": [
                    {"subject": ["class"], "mode": ["trend"], "title_id": None, "knowledge": None, "time_window": "recent_2w"},
                    {"subject": ["student"], "mode": ["portrait"], "title_id": None, "knowledge": None, "time_window": ""},
                ],
                "scope": "all",
                "metric": "",
                "knowledge": None,
                "title_id": None,
                "student_ids": [],
                "classes": [],
                "majors": [],
                "time_window": "recent_2w",
                "needs_clarification": True,
                "clarification_question": "请先在界面框选要分析的学生（张三、李四），或提供学生编号。",
                "is_out_of_domain": False,
            },
            ensure_ascii=False,
        ),
    },
    {"role": "user", "content": "我想了解班级的聚类分布，以及第3题大家的答题时间线和正确率分布。"},
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "intent_type": "overview",
                "sub_goals": [
                    {"subject": ["class"], "mode": ["cluster"], "title_id": None, "knowledge": None, "time_window": ""},
                    {"subject": ["question"], "mode": ["detail"], "title_id": "3", "knowledge": None, "time_window": ""},
                ],
                "scope": "all",
                "metric": "",
                "knowledge": None,
                "title_id": "3",
                "student_ids": [],
                "classes": [],
                "majors": [],
                "time_window": "",
                "needs_clarification": False,
                "clarification_question": "",
                "is_out_of_domain": False,
            },
            ensure_ascii=False,
        ),
    },
    {"role": "user", "content": "什么是链表？"},
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "intent_type": "overview",
                "subject": ["class"],
                "mode": ["portrait"],
                "scope": "all",
                "metric": "",
                "knowledge": None,
                "title_id": None,
                "student_ids": [],
                "classes": [],
                "majors": [],
                "time_window": "",
                "needs_clarification": False,
                "clarification_question": "",
                "is_out_of_domain": True,
            },
            ensure_ascii=False,
        ),
    },
    {"role": "user", "content": "学生心情不好怎么办？"},
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "intent_type": "overview",
                "subject": ["class"],
                "mode": ["portrait"],
                "scope": "all",
                "metric": "",
                "knowledge": None,
                "title_id": None,
                "student_ids": [],
                "classes": [],
                "majors": [],
                "time_window": "",
                "needs_clarification": False,
                "clarification_question": "",
                "is_out_of_domain": True,
            },
            ensure_ascii=False,
        ),
    },
]


def get_system_prompt():
    return SYSTEM_PROMPT


def get_answer_instruction(tool_summaries: str):
    return (
        "以下为已调用的工具返回摘要，请据此生成简短结论与 1～3 条行动建议。\n\n"
        + tool_summaries
        + "\n\n"
        + OUTPUT_FORMAT_INSTRUCTION
    )


def get_intent_parse_system_prompt() -> str:
    return """你是教师学情分析助手，负责将教师自然语言问题解析为结构化意图。

你必须只从下面列出的合法离散值中选择，不得发明新值。

## 三轴枚举

【subject】分析主体，你在看“什么”（数组，可多选）
- student：关注某个或某些学生个体
- question：关注某道或某类题目
- knowledge：关注某个知识点
- class：关注班级整体

【mode】分析模式，用“什么视角”分析（数组，可多选）
- trend：时序趋势、近期变化
- portrait：综合画像、静态快照
- cluster：群体分层、聚类分布
- detail：细粒度明细、过程记录

【scope】粒度范围（单选，最终由系统根据 student_ids / title_id / classes / majors 自动推导）
- individual / selected / all

## 复合目标（重要）
当用户一句话里包含多个分析维度或先后顺序时，必须用 **sub_goals** 数组逐项输出，每项一个 subject 和 mode，按用户说的先后顺序排列。
- 不要合并成一项，不要只保留第一项或“最显眼”的一项。
- 例如：「先看班级趋势，再看学生画像」→ sub_goals 里要有两阶段；「班级聚类以及第3题答题情况」→ 两阶段，且第二阶段的 title_id 填 "3"。
- 只要用户提到题目编号、知识点、时间范围，必须在对应阶段或顶层填写 title_id、knowledge、time_window，不要遗漏。
若只有单一意图，可只输出 subject 和 mode（不输出 sub_goals），系统会自动转为单阶段。

sub_goals 每项格式：{"subject": ["class"], "mode": ["trend"], "title_id": null, "knowledge": null, "time_window": "recent_2w"}

## 特殊标记
- is_out_of_domain=true：问题与学情数据无关时使用。
- needs_clarification=true：需要用户补充关键信息（学生、知识点、时间、班级、题目等）时设为 true，并在 clarification_question 里写一句追问（用户会直接看到）。

## 输出要求
1. 只输出 JSON，不要解释、前后缀、Markdown 或代码块。
2. subject 和 mode 必须为数组，仅使用枚举值。
3. 枚举：subject ∈ ["student", "question", "knowledge", "class"]；mode ∈ ["trend", "portrait", "cluster", "detail"]。
4. 复合意图必须用 sub_goals 按顺序列出各阶段，每阶段 subject/mode 非空且合法。
5. 单意图可不填 sub_goals，系统会从 subject/mode 生成单阶段。

## 输出 JSON 模板（单意图示例）
{
  "intent_type": "overview",
  "subject": ["class"],
  "mode": ["portrait"],
  "scope": "all",
  "metric": "",
  "knowledge": null,
  "title_id": null,
  "student_ids": [],
  "classes": [],
  "majors": [],
  "time_window": "",
  "needs_clarification": false,
  "clarification_question": "",
  "is_out_of_domain": false
}
"""


def get_intent_few_shots() -> list:
    return INTENT_FEW_SHOTS


def get_react_agent_system_prompt():
    return (
        get_system_prompt()
        + "\n你正在执行受控 ReAct 流程。流程分为 planning、act、final_answer 三个阶段。"
        + "\n在 planning 阶段只能推理和规划，不得调用工具。"
        + "\n在 act 阶段由系统执行你规划好的工具，你不能跳过 planning 直接进入 act。"
        + "\n在 final_answer 阶段只能基于已有 observation 输出 JSON 结论，不得新增工具调用。"
    )


def get_react_planner_instruction(question: str, context: dict, available_tools: list, max_tool_calls: int):
    return (
        "你处于 ReAct 的 planning 阶段，本轮严格禁止调用工具。"
        "\n你需要先判断：现有 observation 是否已足够回答问题；若不足，再规划下一轮最小必要工具。"
        "\n请只输出 JSON，不要输出 Markdown、解释、代码块。"
        '\nJSON 格式固定为：{"reason":"1-2句推理","decision":"call_tool|finish","tool_plan":[{"name":"工具名","arguments":{}}]}'
        "\n约束如下："
        "\n1. decision=finish 时，tool_plan 必须是空数组。"
        "\n2. decision=call_tool 时，tool_plan 必须是 1 到 "
        + str(max_tool_calls)
        + " 个工具。"
        "\n3. 工具名必须来自 available_tools。"
        "\n4. 不要重复规划与前一轮完全相同的工具和参数，除非 reason 中明确说明为什么必须重试。"
        "\n5. 若问题指定了班级、专业、学生、知识点等范围，reason 中必须显式说明当前是否已经覆盖该范围。"
        "\n6. 若当前工具无法支持问题要求的粒度，应选择 finish，而不是随意调用无关工具。"
        "\n7. `get_context_filter` 只用于确认可选班级/专业元数据，不直接回答表现趋势；只有当你确实需要校验范围时才使用。"
        "\n8. `query_weekly_trend` 适合回答“近期/最近两周/趋势如何”，不要把它当成任意筛选工具。"
        "\n\n教师问题："
        + (question or "")
        + "\n\n当前上下文："
        + json.dumps(context or {}, ensure_ascii=False)
        + "\n\navailable_tools:\n"
        + json.dumps(available_tools or [], ensure_ascii=False)
    )


def get_react_synthesis_instruction():
    return (
        "你处于 ReAct 的 final_answer 阶段，本轮严格禁止调用工具。"
        "\n你只能基于已有 observation 生成最终回答。"
        "\n请只输出 JSON，不要输出 Markdown、解释、代码块。"
        '\nJSON 格式固定为：{"answer":"1～3句结论","actions":["建议1","建议2"]}'
        "\n要求："
        "\n1. answer 必须先回答教师问题，再给出简短判断。"
        "\n2. 如果 observation 不能支撑问题要求的粒度，answer 必须包含“当前数据不足以支持该结论”。"
        "\n3. 若问题要求的是某班级/某专业/某学生，但 observation 实际只有全量或其他范围，必须明确写出这个不匹配。"
        "\n4. actions 只保留 0-3 条，必须是基于 observation 的后续建议。"
        "\n5. 不得编造任何未出现在 observation 中的数字、对象或知识点。"
    )


def get_compiler_answer_system_prompt():
    return (
        "你是教师学情分析助手。"
        "你只可基于传入的结构化结果(JSON)生成回答，不得添加外部事实。"
        "若任一结果 coverage.covered=false，回答必须包含“当前数据不足以支持该结论”。"
        "仅输出JSON：{\"answer\":\"...\",\"actions\":[\"...\"]}"
    )
