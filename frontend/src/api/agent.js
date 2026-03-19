import request from '@/utils/request'

const USE_MOCK = import.meta.env.VUE_APP_AGENT_MOCK !== 'false'

/**
 * Mock 完整契约：complete 场景（已达成、关键结论、图表入口、完整 trace）
 */
function getMockResponseComplete(question) {
  const prefix = question ? `针对「${question}」：` : ''
  return {
    answer:
      prefix +
      '最近两周班级整体稳定，但链表相关题表现明显偏弱。建议优先复讲链表遍历与边界处理。',
    evidence: [
      { tool: 'week_analysis', summary: '第3周到第4周链表相关得分下降' },
      {
        tool: 'question_by_knowledge',
        summary: '链表相关题平均分低于总体均值',
      },
    ],
    actions: [
      '优先复讲链表遍历与边界处理',
      '重点关注 cluster 2 中提交次数多但得分低的学生',
    ],
    visual_links: [
      { view: 'QuestionView', params: { knowledge: '链表' } },
      { view: 'WeekView', params: { kind: 1 } },
      {
        view: 'StudentView',
        params: {
          student_ids: ['8b6d1125760bd3939b6e', '63eef37311aaac915a45'],
        },
      },
    ],
    trace: {
      steps: [
        {
          tool: 'query_class',
          params: { mode: 'trend' },
          summary: '班级周趋势数据已获取',
          status: 'ok',
          duration_ms: 45,
          reason: '获取整体趋势',
          coverage: { covered: true },
          quality: { score: 0.9 },
          error: '',
        },
        {
          tool: 'query_question',
          params: { knowledge: '链表', mode: 'dist' },
          summary: '链表题目分布已获取',
          status: 'ok',
          duration_ms: 32,
          reason: '按知识点分析',
          coverage: { covered: true },
          quality: { score: 0.85 },
          error: '',
        },
      ],
    },
    goal_check: {
      is_satisfied: true,
      can_stop_early: true,
      reason: '所有关键子目标均已有有效结果支撑。',
      missing_requirements: [],
      supporting_task_ids: ['t1', 't2'],
      confidence: 0.8,
    },
    summary: {
      overall_status: 'complete',
      completed_task_ids: ['t1', 't2'],
      failed_task_ids: [],
      partial_task_ids: [],
      key_findings: [
        '班级整体趋势较为稳定',
        '链表相关题平均分低于总体均值',
        '建议关注 cluster 2 中得分偏低学生',
      ],
      unresolved_points: [],
    },
  }
}

/**
 * Mock partial 场景：未完全达成、有缺失、有未解决点
 */
function getMockResponsePartial(question) {
  const prefix = question ? `针对「${question}」：` : ''
  return {
    answer:
      prefix +
      '当前仅获取到班级趋势数据，学生画像因缺少学生范围暂未执行。请先选择要分析的学生或班级。',
    evidence: [
      { tool: 'query_class', summary: '班级周趋势已获取' },
    ],
    actions: [
      '在左侧选择学生或班级后再次提问',
      '或直接问：最近两周班级整体趋势如何？',
    ],
    visual_links: [
      { view: 'WeekView', params: { kind: 1 } },
    ],
    trace: {
      steps: [
        {
          tool: 'query_class',
          params: { mode: 'trend' },
          summary: '班级趋势数据已获取',
          status: 'ok',
          duration_ms: 38,
          reason: '先获取整体',
          coverage: { covered: true },
          quality: { score: 0.9 },
          error: '',
        },
        {
          tool: 'query_student',
          params: { mode: 'portrait' },
          summary: '未执行：缺少 student_ids',
          status: 'fail',
          duration_ms: 0,
          reason: '学生画像依赖选中学生',
          coverage: { covered: false, reason: '缺少学生范围' },
          quality: {},
          error: '缺少 student_ids，无法执行学生画像',
        },
      ],
    },
    goal_check: {
      is_satisfied: false,
      can_stop_early: false,
      reason: '仍有子目标未被有效结果覆盖。',
      missing_requirements: ['student/portrait'],
      supporting_task_ids: ['t1'],
      confidence: 0.4,
    },
    summary: {
      overall_status: 'partial',
      completed_task_ids: ['t1'],
      failed_task_ids: ['t2'],
      partial_task_ids: [],
      key_findings: ['班级周趋势已获取'],
      unresolved_points: ['缺少 student_ids，无法执行学生画像'],
    },
  }
}

/**
 * 根据问题关键词选择 complete 或 partial mock（便于前端联调两种体验）
 */
function getMockResponse(question) {
  const q = (question || '').toLowerCase()
  if (q.includes('不完整') || q.includes('部分') || q.includes('partial')) {
    return getMockResponsePartial(question)
  }
  return getMockResponseComplete(question)
}

/** Mock 模拟等待时长（毫秒） */
const MOCK_DELAY_MS = 2000

/**
 * 调用 Agent 问答接口
 * @param {string} question - 用户问题
 * @param {object} [context] - 可选上下文 { classes?, majors?, selected_student_ids? }
 * @returns {Promise<{ answer, evidence, actions, visual_links, trace? }>}
 */
export function postAgentQuery(question, context = {}) {
  if (USE_MOCK) {
    return new Promise((resolve) => {
      setTimeout(() => resolve(getMockResponse(question)), MOCK_DELAY_MS)
    })
  }
  console.log('postAgentQuery', question, context)
  // 后续联调时改为真实请求
  return request
    .post('/agent/query', { question, context })
    .then((res) => res.data)
}
