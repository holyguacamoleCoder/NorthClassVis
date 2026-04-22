# 规划策略：简单规则策略（查表展开），后续可扩展 ToT 等。

import json
from itertools import permutations
from typing import Any, Dict, List, Optional, Tuple

from agent.common import extract_first_json_object
from agent.common.llm_client import LLMClient
from agent.common.llm_client import get_default_llm_client
from agent.common.log_config import ensure_agent_logger
from agent.intent.schemas import GoalSpec
from agent.plan.schemas import SubTask
from agent.plan.schemas import TaskGraph

_agent_logger = ensure_agent_logger()

# (subject, mode) -> 语义任务表：每项含 tool、base_params、inputs/outputs、执行/终止条件、验证规则
def _spec(tool: str, base_params: dict, outputs: list, inputs=None, termination_condition="status==ok", verification_rule="", purpose=""):
    return {
        "tool": tool,
        "base_params": base_params,
        "outputs": outputs,
        "inputs": inputs or [],
        "termination_condition": termination_condition,
        "verification_rule": verification_rule or "data is not None",
        "purpose": purpose or f"{tool}",
    }

INTENT_PLAN_MAP = {
    ("student", "portrait"): [
        _spec("query_student", {"mode": "portrait"}, ["student_profile_data"], ["student_ids"], "status==ok", "data is not None", "获取学生画像数据"),
    ],
    ("student", "trend"): [
        _spec("query_student", {"mode": "trend"}, ["student_trend_data"], ["student_ids"], "status==ok", "data is not None", "获取学生趋势数据"),
    ],
    ("student", "detail"): [
        _spec("query_student", {"mode": "tree"}, ["student_tree_data"], ["student_ids"], "status==ok", "data is not None", "获取学生树结构"),
        _spec("query_student", {"mode": "detail"}, ["student_detail_data"], ["student_ids"], "status==ok", "data is not None", "获取学生详情"),
    ],
    ("question", "portrait"): [
        _spec("query_question", {"mode": "list"}, ["question_list_data"], ["title_id"], "status==ok", "data is not None", "获取题目列表"),
    ],
    ("question", "detail"): [
        _spec("query_question", {"mode": "timeline"}, ["question_timeline_data"], ["title_id"], "status==ok", "data is not None", "获取题目时间线"),
        _spec("query_question", {"mode": "dist"}, ["question_dist_data"], ["title_id"], "status==ok", "data is not None", "获取题目分布"),
    ],
    ("knowledge", "portrait"): [
        _spec("query_knowledge", {}, ["knowledge_portrait_data"], ["knowledge"], "status==ok", "data is not None", "获取知识点画像"),
    ],
    ("class", "trend"): [
        _spec("query_class", {"mode": "trend"}, ["class_trend_data"], [], "status==ok", "data is not None", "获取班级趋势数据"),
    ],
    ("class", "detail"): [
        _spec("query_class", {"mode": "detail"}, ["class_detail_data"], [], "status==ok", "data is not None", "获取班级细粒度趋势数据"),
    ],
    ("class", "cluster"): [
        _spec("query_class", {"mode": "cluster"}, ["class_cluster_data"], [], "status==ok", "data is not None", "获取班级聚类数据"),
    ],
    ("class", "portrait"): [
        _spec("query_class", {"mode": "trend"}, ["class_portrait_data"], [], "status==ok", "data is not None", "获取班级画像数据"),
    ]
}

_FALLBACK_SPEC = _spec("query_class", {"mode": "trend"}, ["class_trend_data"], [], "status==ok", "data is not None", "overview fallback")
MAX_TOKENS = 1024


def _subtask_from_spec(spec: dict, task_id: str, s: str, m: str, params: dict, dependencies=None, priority=100, reason="", purpose_override=""):
    """从语义表 spec 构造 SubTask，填满 inputs/outputs/termination_condition/verification_rule。"""
    tool_name = spec["tool"]
    purpose = purpose_override or spec.get("purpose") or f"{s}/{m} -> {tool_name}"
    inputs = {"slots": spec.get("inputs", [])} if spec.get("inputs") else {}
    return SubTask(
        task_id=task_id,
        name=tool_name,
        purpose=purpose,
        inputs=inputs,
        outputs=spec.get("outputs", []),
        required_tools=[tool_name],
        tool_params=params,
        dependencies=dependencies or [],
        execution_condition=spec.get("execution_condition", ""),
        termination_condition=spec.get("termination_condition", ""),
        verification_rule=spec.get("verification_rule", ""),
        priority=priority,
        reason=reason,
    )


def _merge_step_params(
    tool_name: str,
    base_params: dict,
    goal: GoalSpec,
    phase_override: Optional[Dict[str, Any]] = None,
) -> dict:
    """将 base_params 与 goal 槽位合并；phase_override 可覆盖该阶段的 title_id、knowledge、time_window。"""
    p = dict(base_params)
    title_id = (phase_override or {}).get("title_id") if phase_override else None
    if title_id is None:
        title_id = goal.title_id
    knowledge = (phase_override or {}).get("knowledge") if phase_override else None
    if knowledge is None:
        knowledge = goal.knowledge
    if tool_name == "query_student":
        if goal.student_ids:
            p["student_ids"] = list(goal.student_ids)
    elif tool_name == "query_question":
        if knowledge:
            p["knowledge"] = knowledge
        if title_id:
            p["title_id"] = title_id
        p.setdefault("limit", 20)
    elif tool_name == "query_knowledge":
        p["knowledge"] = knowledge or ""
    return p


class SimpleRuleStrategy:
    """
    简单规则策略：按 goal.subject × goal.mode 查表展开为无依赖子任务，
    全部放入同一批（当前执行器按顺序跑，后续可并行）。
    """

    def plan(self, goal: GoalSpec) -> TaskGraph:
        graph = TaskGraph()
        seen: set = set()
        idx = 0
        for s in goal.subject or ["class"]:
            for m in goal.mode or ["portrait"]:
                plan_specs = INTENT_PLAN_MAP.get((s, m))
                if not plan_specs:
                    continue
                for spec in plan_specs:
                    tool_name, base_params = spec["tool"], spec["base_params"]
                    params = _merge_step_params(tool_name, base_params, goal)
                    key = (
                        tool_name,
                        tuple(
                            (k, tuple(v) if isinstance(v, list) else v)
                            for k, v in sorted(params.items())
                        ),
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    task_id = f"t{idx}"
                    idx += 1
                    graph.add_task(_subtask_from_spec(
                        spec, task_id, s, m, params,
                        priority=100,
                        reason=f"{s}/{m} -> {tool_name}",
                    ))
        if not graph.tasks:
            params = _merge_step_params(_FALLBACK_SPEC["tool"], _FALLBACK_SPEC["base_params"], goal)
            task_id = f"t{idx}"
            idx += 1
            graph.add_task(_subtask_from_spec(
                _FALLBACK_SPEC, task_id, "class", "trend", params,
                priority=100,
                reason="overview fallback",
                purpose_override="overview fallback",
            ))
        return graph


def _expand_phase(
    phase: Dict[str, Any],
    goal: GoalSpec,
    start_idx: int,
    seen: set,
) -> Tuple[List[SubTask], int]:
    """
    将单个阶段（phase）展开为 SubTask 列表。
    phase 含 subject(list), mode(list)，可选 title_id, knowledge, time_window。
    返回 (SubTask 列表, 下一个可用 idx)。
    """
    tasks: List[SubTask] = []
    idx = start_idx
    subjects = phase.get("subject") or goal.subject or ["class"]
    modes = phase.get("mode") or goal.mode or ["portrait"]
    if not isinstance(subjects, list):
        subjects = [subjects]
    if not isinstance(modes, list):
        modes = [modes]
    phase_override = {k: phase[k] for k in ("title_id", "knowledge", "time_window") if k in phase and phase[k] is not None}
    if not phase_override:
        phase_override = None
    for s in subjects:
        for m in modes:
            plan_specs = INTENT_PLAN_MAP.get((s, m))
            if not plan_specs:
                continue
            for spec in plan_specs:
                tool_name, base_params = spec["tool"], spec["base_params"]
                params = _merge_step_params(tool_name, base_params, goal, phase_override)
                key = (
                    tool_name,
                    tuple(
                        (k, tuple(v) if isinstance(v, list) else v)
                        for k, v in sorted(params.items())
                    ),
                )
                if key in seen:
                    continue
                seen.add(key)
                task_id = f"t{idx}"
                idx += 1
                tasks.append(
                    _subtask_from_spec(
                        spec, task_id, s, m, params,
                        priority=100,
                        reason=f"CoT {s}/{m} -> {tool_name}",
                    )
                )
    if not tasks:
        spec = _FALLBACK_SPEC
        tool_name, base_params = spec["tool"], spec["base_params"]
        params = _merge_step_params(tool_name, base_params, goal, phase_override)
        key = (
            tool_name,
            tuple((k, tuple(v) if isinstance(v, list) else v) for k, v in sorted(params.items())),
        )
        if key not in seen:
            seen.add(key)
            tasks.append(
                _subtask_from_spec(
                    spec, f"t{idx}", "class", "trend", params,
                    priority=50,
                    reason="CoT fallback",
                    purpose_override="CoT fallback",
                )
            )
            idx += 1
    return tasks, idx


def _build_graph_from_sub_goals(
    goal: GoalSpec,
    sub_goals_override: Optional[List[Dict[str, Any]]] = None,
) -> TaskGraph:
    """
    按 sub_goals 顺序展开为 DAG：每阶段内无依赖，阶段间前一阶段所有任务指向本阶段所有任务。
    sub_goals_override 若提供则替代 goal.sub_goals（用于 CoT 推理后的重排结果）。
    """
    graph = TaskGraph()
    sub_goals = sub_goals_override if sub_goals_override is not None else (goal.sub_goals or [])
    if not sub_goals:
        sub_goals = [{"subject": list(goal.subject or ["class"]), "mode": list(goal.mode or ["portrait"])}]
    seen: set = set()
    idx = 0
    prev_phase_task_ids: List[str] = []
    for phase in sub_goals:
        phase_tasks, idx = _expand_phase(phase, goal, idx, seen)
        if not phase_tasks:
            continue
        phase_task_ids = [t.task_id for t in phase_tasks]
        for t in phase_tasks:
            t.dependencies = list(prev_phase_task_ids)
            graph.add_task(t)
            for pid in prev_phase_task_ids:
                graph.add_edge(pid, t.task_id)
        prev_phase_task_ids = phase_task_ids
    return graph


def _validate_ordered_phases(
    ordered_phases: Any,
    valid_subjects: set,
    valid_modes: set,
) -> Optional[List[Dict[str, Any]]]:
    """校验 LLM 返回的 ordered_phases 是否合法（每项含 subject/list、mode/list 且在枚举内）。"""
    if not ordered_phases or not isinstance(ordered_phases, list):
        return None
    out = []
    for p in ordered_phases:
        if not p or not isinstance(p, dict):
            return None
        s = p.get("subject")
        m = p.get("mode")
        if not isinstance(s, list):
            s = [s] if s else ["class"]
        if not isinstance(m, list):
            m = [m] if m else ["portrait"]
        if not all(x in valid_subjects for x in s) or not all(x in valid_modes for x in m):
            return None
        out.append({"subject": s, "mode": m})
    return out if out else None


VALID_SUBJECTS = {"student", "question", "knowledge", "class"}
VALID_MODES = {"trend", "portrait", "cluster", "detail"}


class CoTStrategy:
    """
    链式推理策略（CoT）：
    1) 用 LLM 对 sub_goals 做链式推理（为什么先 A 再 B），并输出建议执行顺序；
    2) 按该顺序建 DAG，阶段间加依赖边。
    LLM 不可用或解析失败时，直接按 intent 给的 sub_goals 顺序建图。
    """

    def __init__(self, llm_client=None):
        self._llm_client = llm_client or get_default_llm_client()
        self._fallback = SimpleRuleStrategy()

    def _build_cot_messages(self, goal: GoalSpec, sub_goals: List[Dict[str, Any]]) -> list:
        """构造链式推理 prompt：请给出执行顺序的理由并输出有序阶段。"""
        system = (
            "你是教学分析任务规划助手。用户有一个目标，并已拆成若干分析阶段（phases）。"
            "请用 1～3 句话做链式推理：为什么应按某种顺序执行（例如：先看整体再下钻、先班级再学生）。"
            "然后输出调整后的阶段顺序（可保持原序或重排）。仅输出 JSON，不要其他文字。"
        )
        payload = {
            "goal": goal.to_dict(),
            "phases": sub_goals,
            "output_schema": {
                "reasoning": "1～3 句话说明执行顺序的理由（chain-of-thought）",
                "ordered_phases": "与 phases 同结构的有序数组，每项 { \"subject\": [\"class\"], \"mode\": [\"trend\"] }",
            },
        }
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

    def _cot_reason_and_order(self, goal: GoalSpec) -> Tuple[Optional[List[Dict[str, Any]]], str]:
        """
        调 LLM 做链式推理，返回 (ordered_phases 或 None, reasoning 文案)。
        解析失败或 LLM 不可用时返回 (None, "")。
        """
        sub_goals = goal.sub_goals or []
        if not sub_goals or len(sub_goals) < 2:
            return None, ""
        if not self._llm_client or not getattr(self._llm_client, "config", None) or not self._llm_client.config.is_available():
            return None, ""
        try:
            resp = self._llm_client.chat_text_only(
                self._build_cot_messages(goal, sub_goals),
                max_tokens=MAX_TOKENS,
            )
            text = LLMClient.extract_final_text(resp)
            obj = extract_first_json_object(text) if text else None
            if not obj or not isinstance(obj, dict):
                return None, ""
            reasoning = (obj.get("reasoning") or "").strip()
            ordered = obj.get("ordered_phases")
            validated = _validate_ordered_phases(ordered, VALID_SUBJECTS, VALID_MODES)
            if validated:
                _agent_logger.info("CoTStrategy: 链式推理完成 reasoning=%s", (reasoning or "")[:100])
                return validated, reasoning
            return None, reasoning or ""
        except Exception as e:
            _agent_logger.warning("CoTStrategy 链式推理失败: %s", e)
            return None, ""

    def plan(self, goal: GoalSpec) -> TaskGraph:
        sub_goals = goal.sub_goals or []
        if not sub_goals and goal.subject and goal.mode:
            sub_goals = [{"subject": list(goal.subject), "mode": list(goal.mode)}]
        if len(sub_goals) <= 1:
            _agent_logger.info("CoTStrategy: 单阶段，回退 SimpleRuleStrategy")
            return self._fallback.plan(goal)
        ordered_phases, _ = self._cot_reason_and_order(goal)
        if ordered_phases:
            _agent_logger.info("CoTStrategy: 使用链式推理重排后 %d 阶段建 DAG", len(ordered_phases))
            return _build_graph_from_sub_goals(goal, sub_goals_override=ordered_phases)
        _agent_logger.info("CoTStrategy: 按 intent 原序 sub_goals=%d 建 DAG", len(sub_goals))
        return _build_graph_from_sub_goals(goal)


def _candidate_pairs(goal: GoalSpec) -> List[Tuple[str, str]]:
    """从 goal.subject × goal.mode 得到候选 (s,m) 对（用于无 sub_goals 时）。"""
    pairs = []
    for s in goal.subject or ["class"]:
        for m in goal.mode or ["portrait"]:
            if (s, m) in INTENT_PLAN_MAP:
                pairs.append((s, m))
    if not pairs:
        pairs.append(("class", "trend"))
    return pairs


def _candidate_pairs_from_sub_goals(goal: GoalSpec) -> List[Tuple[str, str]]:
    """
    从 goal.sub_goals 按顺序抽出 (s,m) 作为候选路径，供 ToT 选「最合适路径」而非单 task。
    返回顺序与 sub_goals 一致，便于 LLM 对整条路径打分/重排。
    """
    sub_goals = goal.sub_goals or []
    if len(sub_goals) < 2:
        return []
    pairs: List[Tuple[str, str]] = []
    for phase in sub_goals:
        subjects = phase.get("subject") or goal.subject or ["class"]
        modes = phase.get("mode") or goal.mode or ["portrait"]
        if not isinstance(subjects, list):
            subjects = [subjects]
        if not isinstance(modes, list):
            modes = [modes]
        for s in subjects:
            for m in modes:
                if (s, m) in INTENT_PLAN_MAP:
                    pairs.append((s, m))
    return pairs


def _build_path_plan_candidates(base_path: List[Tuple[str, str]], max_plans: int = 6) -> List[List[Tuple[str, str]]]:
    """
    基于单一路径生成多个候选执行方案（ToT 的“树”）：
    - 原顺序
    - 逆序
    - 启发式顺序（先班级/趋势，再下钻到学生/详情）
    - 小规模时补充若干排列
    """
    if not base_path:
        return []
    if len(base_path) == 1:
        return [list(base_path)]

    subject_order = {"class": 0, "question": 1, "knowledge": 2, "student": 3}
    mode_order = {"trend": 0, "cluster": 1, "portrait": 2, "detail": 3}

    candidates: List[List[Tuple[str, str]]] = [
        list(base_path),
        list(reversed(base_path)),
        sorted(base_path, key=lambda x: (subject_order.get(x[0], 99), mode_order.get(x[1], 99))),
        sorted(base_path, key=lambda x: (mode_order.get(x[1], 99), subject_order.get(x[0], 99))),
    ]

    # 小规模时补充排列，模拟 ToT 多分支搜索空间。
    if len(base_path) <= 4:
        for perm in permutations(base_path):
            candidates.append(list(perm))
            if len(candidates) >= max_plans * 2:
                break

    uniq: List[List[Tuple[str, str]]] = []
    seen = set()
    for p in candidates:
        k = tuple(p)
        if k in seen:
            continue
        seen.add(k)
        uniq.append(p)
        if len(uniq) >= max_plans:
            break
    return uniq


def _build_scored_graph(
    goal: GoalSpec,
    ranked_pairs: List[Tuple[str, str, float, str]],
    fallback_reason: str = "tot fallback",
) -> TaskGraph:
    graph = TaskGraph()
    seen = set()
    idx = 0
    if not ranked_pairs:
        ranked_pairs = [("class", "trend", 0.2, fallback_reason)]
    for s, m, score, reason in ranked_pairs:
        plan_specs = INTENT_PLAN_MAP.get((s, m))
        if not plan_specs:
            continue
        for spec in plan_specs:
            tool_name, base_params = spec["tool"], spec["base_params"]
            params = _merge_step_params(tool_name, base_params, goal)
            key = (
                tool_name,
                tuple((k, tuple(v) if isinstance(v, list) else v) for k, v in sorted(params.items())),
            )
            if key in seen:
                continue
            seen.add(key)
            priority = max(1, min(100, int(score * 100)))
            task_id = f"t{idx}"
            idx += 1
            graph.add_task(
                _subtask_from_spec(
                    spec, task_id, s, m, params,
                    priority=priority,
                    reason=f"ToT[{score:.2f}] {reason or f'{s}/{m}'} -> {tool_name}",
                )
            )
    if not graph.tasks:
        spec = _FALLBACK_SPEC
        params = _merge_step_params(spec["tool"], spec["base_params"], goal)
        graph.add_task(
            _subtask_from_spec(
                spec, "t0", "class", "trend", params,
                priority=20,
                reason=fallback_reason,
                purpose_override="overview fallback",
            )
        )
    return graph


def _build_scored_graph_with_edges(
    goal: GoalSpec,
    ranked_pairs: List[Tuple[str, str, float, str]],
) -> TaskGraph:
    """
    按 ranked_pairs 顺序建 DAG：每个 (s,m) 为一阶段，阶段间加边。
    保证所有策略产出的都是带依赖的图（单阶段时无边）。
    """
    graph = TaskGraph()
    if not ranked_pairs:
        ranked_pairs = [("class", "trend", 0.2, "tot fallback")]
    seen: set = set()
    idx = 0
    prev_phase_task_ids: List[str] = []
    for s, m, score, reason in ranked_pairs:
        phase = {"subject": [s], "mode": [m]}
        phase_tasks, idx = _expand_phase(phase, goal, idx, seen)
        if not phase_tasks:
            continue
        for t in phase_tasks:
            t.priority = max(1, min(100, int(score * 100)))
            t.reason = f"ToT[{score:.2f}] {reason or f'{s}/{m}'} -> {t.name}"
            t.dependencies = list(prev_phase_task_ids)
            graph.add_task(t)
            for pid in prev_phase_task_ids:
                graph.add_edge(pid, t.task_id)
        prev_phase_task_ids = [t.task_id for t in phase_tasks]
    if not graph.tasks:
        spec = _FALLBACK_SPEC
        params = _merge_step_params(spec["tool"], spec["base_params"], goal)
        graph.add_task(
            _subtask_from_spec(
                spec, "t0", "class", "trend", params,
                priority=20,
                reason="tot fallback",
                purpose_override="overview fallback",
            )
        )
    return graph


class ToTStrategy:
    """
    ToT 轻量实现：
    - 当有多阶段 sub_goals 时：把候选视为**一条路径**，让 LLM 评估路径顺序是否合理并可选调整顺序（不按单分支打分）；
    - 否则：枚举分支，LLM 挑选并打分，按得分建图。
    """

    def __init__(self, llm_client=None):
        self._llm_client = llm_client or get_default_llm_client()
        self._fallback = SimpleRuleStrategy()
        self._last_tot_debug: Dict[str, Any] = {}

    def get_last_tot_debug(self) -> Dict[str, Any]:
        """返回最近一次 ToT 路径评选调试信息（只读副本）。"""
        return dict(self._last_tot_debug)

    def _build_messages_path(self, goal: GoalSpec, plan_candidates: List[List[Tuple[str, str]]]):
        """路径模式：输入多个候选路径，让 LLM 评选最优执行方案。"""
        plans = []
        for idx, path in enumerate(plan_candidates):
            plans.append(
                {
                    "plan_id": f"p{idx}",
                    "phases": [{"subject": s, "mode": m} for s, m in path],
                }
            )
        payload = {
            "goal": goal.to_dict(),
            "plan_candidates": plans,
            "说明": "请比较多个候选路径并评选最优方案；可返回前 1~3 个方案及理由。",
            "output_schema": {
                "selected_plans": [
                    {
                        "plan_id": "p0",
                        "score": "0~1 float",
                        "reason": "string",
                    }
                ]
            },
        }
        system = (
            "你是教学分析任务规划器。请在多个候选路径中评选最优方案，核心看执行顺序是否合理。"
            "优先考虑：先整体再个体、先趋势再下钻、先班级再学生。"
            "仅输出 JSON，不要其他文字。plan_id 必须来自输入。"
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

    def _build_messages_branches(self, goal: GoalSpec, candidates: List[Tuple[str, str]]):
        """分支模式：无路径时，从候选中挑选并打分。"""
        payload = {
            "goal": goal.to_dict(),
            "candidates": [{"subject": s, "mode": m} for s, m in candidates],
            "output_schema": {
                "selected": [{"subject": "string", "mode": "string", "score": "0~1 float", "reason": "string"}]
            },
        }
        system = (
            "你是教学分析任务规划器。请从候选分支中挑选最相关的1~3个分支并打分，"
            "仅输出 JSON。score 越高表示越应优先执行。"
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

    def _llm_rank_pairs(
        self, goal: GoalSpec, candidates: List[Tuple[str, str]], use_path: bool = False
    ) -> List[Tuple[str, str, float, str]]:
        """
        use_path=True：路径模式，LLM 输出 ordered_phases，按该顺序返回（不按分数排序）。
        use_path=False：分支模式，LLM 输出 selected 带 score，按分数排序后返回。
        """
        if not self._llm_client or not self._llm_client.config.is_available():
            return []
        valid_pairs = set(candidates)
        try:
            if use_path and len(candidates) >= 2:
                return self._llm_evaluate_path(goal, candidates, valid_pairs)
            return self._llm_select_branches(goal, candidates, valid_pairs)
        except Exception as e:
            _agent_logger.warning("ToTStrategy LLM rank 失败，fallback 规则策略: %s", e)
            return []

    def _llm_evaluate_path(
        self, goal: GoalSpec, path_candidates: List[Tuple[str, str]], valid_pairs: set
    ) -> List[Tuple[str, str, float, str]]:
        """路径评估：构造多候选路径，LLM 评选最优方案后按方案顺序返回。"""
        plan_candidates = _build_path_plan_candidates(path_candidates)
        if not plan_candidates:
            return []
        plan_map = {f"p{i}": p for i, p in enumerate(plan_candidates)}
        _agent_logger.info("ToTStrategy: 路径候选方案数=%d", len(plan_candidates))
        self._last_tot_debug = {
            "plan_candidates": {pid: list(path) for pid, path in plan_map.items()},
            "selected_plans": [],
            "chosen_plan": None,
        }
        resp = self._llm_client.chat_text_only(
            self._build_messages_path(goal, plan_candidates), max_tokens=MAX_TOKENS
        )
        text = LLMClient.extract_final_text(resp)
        obj = extract_first_json_object(text) if text else None
        selected_plans = (obj or {}).get("selected_plans") if isinstance(obj, dict) else None
        if not isinstance(selected_plans, list) or not selected_plans:
            return []
        score_logs: List[str] = []
        normalized_selected: List[Dict[str, Any]] = []
        best_plan_id = None
        best_score = -1.0
        best_reason = "ToT 路径评选"
        for item in selected_plans:
            if not isinstance(item, dict):
                continue
            plan_id = item.get("plan_id")
            if plan_id not in plan_map:
                continue
            try:
                score = float(item.get("score", 0.5))
            except Exception:
                score = 0.5
            reason = str(item.get("reason") or "").strip()
            normalized_selected.append(
                {
                    "plan_id": plan_id,
                    "score": max(0.0, min(1.0, score)),
                    "reason": reason,
                    "path": plan_map.get(plan_id, []),
                }
            )
            reason_short = (reason[:40] + "...") if len(reason) > 40 else reason
            score_logs.append(f"{plan_id}:{max(0.0, min(1.0, score)):.2f}({reason_short})")
            if score > best_score:
                best_score = score
                best_plan_id = plan_id
                best_reason = reason or best_reason
        if score_logs:
            _agent_logger.info("ToTStrategy: 多方案评分=%s", " | ".join(score_logs))
        if not best_plan_id:
            return []
        chosen_path = plan_map[best_plan_id]
        _agent_logger.info("ToTStrategy: 选中方案=%s score=%.2f", best_plan_id, max(0.0, min(1.0, best_score)))
        self._last_tot_debug = {
            "plan_candidates": {pid: list(path) for pid, path in plan_map.items()},
            "selected_plans": normalized_selected,
            "chosen_plan": best_plan_id,
            "chosen_score": max(0.0, min(1.0, best_score)),
            "chosen_reason": best_reason,
            "chosen_path": list(chosen_path),
        }
        ranked = []
        seen_pairs = set()
        clamped_score = max(0.0, min(1.0, best_score))
        for s, m in chosen_path:
            pair = (s, m)
            if pair not in valid_pairs or pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            ranked.append((s, m, clamped_score, f"{best_plan_id} {best_reason}"))
        return ranked

    def _llm_select_branches(
        self, goal: GoalSpec, candidates: List[Tuple[str, str]], valid_pairs: set
    ) -> List[Tuple[str, str, float, str]]:
        """分支选择：解析 selected，按 score 排序后返回。"""
        resp = self._llm_client.chat_text_only(
            self._build_messages_branches(goal, candidates), max_tokens=MAX_TOKENS
        )
        text = LLMClient.extract_final_text(resp)
        obj = extract_first_json_object(text) if text else None
        selected = (obj or {}).get("selected") if isinstance(obj, dict) else None
        if not isinstance(selected, list):
            return []
        ranked = []
        for item in selected:
            if not isinstance(item, dict):
                continue
            s = item.get("subject")
            m = item.get("mode")
            if isinstance(s, list):
                s = s[0] if s else None
            if isinstance(m, list):
                m = m[0] if m else None
            if (s, m) not in valid_pairs:
                continue
            try:
                score = float(item.get("score", 0.5))
            except Exception:
                score = 0.5
            reason = str(item.get("reason") or "").strip()
            ranked.append((s, m, max(0.0, min(1.0, score)), reason))
        ranked.sort(key=lambda x: x[2], reverse=True)
        return ranked[:3]

    def plan(self, goal: GoalSpec) -> TaskGraph:
        self._last_tot_debug = {}
        sub_goals = goal.sub_goals or []
        candidates = _candidate_pairs(goal)
        use_path = False
        if len(sub_goals) >= 2:
            from_sub = _candidate_pairs_from_sub_goals(goal)
            if from_sub:
                candidates = from_sub
                use_path = True
        _agent_logger.info("ToTStrategy: 候选=%s use_path=%s", candidates, use_path)
        ranked = self._llm_rank_pairs(goal, candidates, use_path=use_path)
        if not ranked:
            _agent_logger.info("ToTStrategy: 未拿到有效排序，回退 SimpleRuleStrategy")
            return self._fallback.plan(goal)
        _agent_logger.info("ToTStrategy: 选中路径/分支=%s，按序建 DAG", ranked)
        return _build_scored_graph_with_edges(goal, ranked_pairs=ranked)
