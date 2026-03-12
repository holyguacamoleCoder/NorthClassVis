import request from '@/utils/request'

const USE_MOCK = process.env.VUE_APP_AGENT_MOCK !== 'false'

/**
 * Mock 响应，覆盖契约字段，便于渲染对话与运行轨迹
 */
function getMockResponse(question) {
  const prefix = question ? `针对「${question}」：` : ''
  return {
    answer: prefix + '最近两周班级整体稳定，但链表相关题表现明显偏弱。建议优先复讲链表遍历与边界处理。',
    evidence: [
      { tool: 'week_analysis', summary: '第3周到第4周链表相关得分下降' },
      { tool: 'question_by_knowledge', summary: '链表相关题平均分低于总体均值' },
    ],
    actions: [
      '优先复讲链表遍历与边界处理',
      '重点关注 cluster 2 中提交次数多但得分低的学生',
    ],
    visual_links: [
      { view: 'QuestionView', params: { knowledge: '链表' } },
      { view: 'WeekView', params: { kind: 1 } },
      { view: 'StudentView', params: { student_ids: ['8b6d1125760bd3939b6e', '63eef37311aaac915a45'] } },
    ],
    trace: {
      steps: [
        { tool: 'week_analysis', params: { student_ids: [] }, summary: '周趋势数据已获取' },
        { tool: 'question_by_knowledge', params: { knowledge: '链表' }, summary: '题目列表已获取' },
      ],
    },
  }
}

/**
 * 调用 Agent 问答接口
 * @param {string} question - 用户问题
 * @param {object} [context] - 可选上下文 { classes?, majors?, selected_student_ids? }
 * @returns {Promise<{ answer, evidence, actions, visual_links, trace? }>}
 */
export function postAgentQuery(question, context = {}) {
  if (USE_MOCK) {
    return Promise.resolve(getMockResponse(question))
  }
  console.log('postAgentQuery', question, context)
  // 后续联调时改为真实请求
  return request.post('/agent/query', { question, context }).then(res => res.data)
}
