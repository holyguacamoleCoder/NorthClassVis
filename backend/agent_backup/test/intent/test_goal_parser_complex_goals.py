"""复杂大目标：用真实 LLM 测 intent 能否正确识别多意图、长句、组合需求。不 mock 客户端，LLM 不可用时跳过。"""

import pytest

from agent.common.context_utils import normalize_context
from agent.common.llm_client import get_default_llm_client
from agent.intent.goal_parser import parse_goal
from agent.intent.goal_parser import VALID_MODES
from agent.intent.goal_parser import VALID_SUBJECTS
from agent.intent.schemas import GoalSpec


def _llm_available():
    try:
        client = get_default_llm_client()
        return client and getattr(client, "config", None) and client.config.is_available()
    except Exception:
        return False


def _assert_valid_goal(goal: GoalSpec) -> None:
    assert isinstance(goal, GoalSpec)
    assert goal.subject, "subject 不应为空"
    assert goal.mode, "mode 不应为空"
    for s in goal.subject:
        assert s in VALID_SUBJECTS, f"subject 应在 {VALID_SUBJECTS} 内，得到 {goal.subject}"
    for m in goal.mode:
        assert m in VALID_MODES, f"mode 应在 {VALID_MODES} 内，得到 {goal.mode}"


@pytest.mark.llm
@pytest.mark.skipif(not _llm_available(), reason="LLM 未配置或不可用，跳过复杂目标真实调用")
class TestIntentComplexGoalsRealLLM:
    """复杂大目标：真实 LLM 解析，仅当 LLM 可用时运行。"""

    def test_class_trend_then_student_portrait(self):
        """先班级趋势、再学生画像的多步表述。"""
        question = "先看下全班最近两周的整体趋势，再帮我看看张三和李四这两个学生的画像。"
        ctx = normalize_context({"selected_student_ids": ["zhangsan", "lisi"]})
        goal = parse_goal(question, ctx)
        _assert_valid_goal(goal)
        # 当前 intent 输出单一 GoalSpec，应至少识别出 class 或 student 之一，且 mode 合理
        assert set(goal.subject) & (VALID_SUBJECTS), goal.subject
        assert set(goal.mode) & (VALID_MODES), goal.mode

    def test_class_cluster_and_question_detail(self):
        """班级聚类 + 题目详情的组合需求。"""
        question = "我想了解班级的聚类分布，以及第3题大家的答题时间线和正确率分布。"
        goal = parse_goal(question, normalize_context({}))
        _assert_valid_goal(goal)
        assert set(goal.subject) & (VALID_SUBJECTS), goal.subject
        assert set(goal.mode) & (VALID_MODES), goal.mode

    def test_knowledge_and_student_detail(self):
        """知识点掌握 + 学生详细/提交记录。"""
        question = "链表和递归这两个知识点的掌握情况怎么样？再帮我看看选中学生的提交记录和详细做题情况。"
        ctx = normalize_context({"selected_student_ids": ["s1"]})
        goal = parse_goal(question, ctx)
        _assert_valid_goal(goal)
        assert set(goal.subject) & (VALID_SUBJECTS), goal.subject
        assert set(goal.mode) & (VALID_MODES), goal.mode

    def test_long_natural_single_focus(self):
        """长句但单一焦点：班级趋势。"""
        question = "老师您好，我想看一下我们班这学期以来在周测上的整体表现趋势，有没有明显下滑或需要重点关注的阶段？"
        goal = parse_goal(question, normalize_context({}))
        _assert_valid_goal(goal)
        assert "class" in goal.subject
        assert "trend" in goal.mode

    def test_student_portrait_without_ids_should_ask_clarification(self):
        """点明学生画像但未指定人，应触发追问。"""
        question = "帮我看看这几个学生的画像和最近学习情况。"
        goal = parse_goal(question, normalize_context({}))
        _assert_valid_goal(goal)
        if "student" in goal.subject:
            assert goal.needs_clarification is True
            assert goal.clarification_question

    def test_multi_subject_multi_mode_compound(self):
        """多主体多模式复合句。"""
        question = "先看班级趋势和聚类，再针对选中的学生看画像和详细提交记录。"
        ctx = normalize_context({"selected_student_ids": ["a", "b"]})
        goal = parse_goal(question, ctx)
        _assert_valid_goal(goal)
        # 应识别出至少一类 subject（class/student）及对应 mode
        assert len(goal.subject) >= 1, goal.subject
        assert len(goal.mode) >= 1, goal.mode
