import request from '@/utils/request'

const USE_MOCK = import.meta.env.VUE_APP_AGENT_MOCK !== 'false'
const JOB_POLL_MS = 400
const JOB_POLL_MS_FAST = 250
const JOB_TIMEOUT_MS = 180000

export class JobAbortedError extends Error {
  constructor(message = '已停止生成') {
    super(message)
    this.name = 'JobAbortedError'
  }
}

export function createJobAbortHandle() {
  let aborted = false
  let jobId = null
  return {
    setJobId(id) {
      jobId = id
    },
    getJobId() {
      return jobId
    },
    abort() {
      aborted = true
    },
    isAborted() {
      return aborted
    },
    reset() {
      aborted = false
      jobId = null
    },
  }
}

/** Mock 完整契约：complete 场景 */
function getMockResponseComplete(question) {
  const prefix = question ? `针对「${question}」：` : ''
  return {
    answer:
      prefix +
      '最近两周班级整体稳定，但链表相关题表现明显偏弱。建议优先复讲链表遍历与边界处理。',
    evidence: [
      { tool: 'week_analysis', summary: '第3周到第4周链表相关得分下降' },
      { tool: 'question_by_knowledge', summary: '链表相关题平均分低于总体均值' },
    ],
    actions: ['优先复讲链表遍历与边界处理'],
    visual_links: [
      { view: 'QuestionView', params: { knowledge: '链表' } },
      { view: 'WeekView', params: { kind: 1 } },
    ],
    trace: {
      steps: [
        {
          tool: 'query_data',
          params: { resource: 'week_aggregation' },
          summary: '班级周趋势数据已获取',
          status: 'ok',
          duration_ms: 45,
        },
      ],
    },
    goal_check: { is_satisfied: true, can_stop_early: true, reason: '' },
    summary: {
      overall_status: 'complete',
      key_findings: ['班级整体趋势较为稳定'],
      unresolved_points: [],
    },
  }
}

function getMockResponse(question) {
  return getMockResponseComplete(question)
}

const MOCK_DELAY_MS = 1500

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export async function listAgentSessions() {
  const res = await request.get('/agent/sessions')
  return res.data
}

export async function listAgentSkills() {
  const res = await request.get('/agent/skills')
  return res.data
}

export async function createAgentSession(payload = {}) {
  const res = await request.post('/agent/sessions', payload)
  return res.data
}

export async function getAgentSession(sessionId) {
  const res = await request.get(`/agent/sessions/${sessionId}`)
  return res.data
}

export async function updateAgentSession(sessionId, payload) {
  const res = await request.patch(`/agent/sessions/${sessionId}`, payload)
  return res.data
}

export async function deleteAgentSession(sessionId) {
  const res = await request.delete(`/agent/sessions/${sessionId}`)
  return res.data
}

export async function activateAgentSession(sessionId) {
  const res = await request.post(`/agent/sessions/${sessionId}/activate`)
  return res.data
}

export async function submitAgentMessage(sessionId, content, context = {}) {
  const res = await request.post(`/agent/sessions/${sessionId}/messages`, {
    content,
    context,
  })
  return res.data
}

export async function getAgentJob(jobId) {
  const res = await request.get(`/agent/jobs/${jobId}`)
  return res.data
}

export async function cancelAgentJob(jobId) {
  const res = await request.post(`/agent/jobs/${jobId}/cancel`)
  return res.data
}

export async function listAgentMemories() {
  const res = await request.get('/agent/memories')
  return res.data
}

export async function createAgentMemory(payload) {
  const res = await request.post('/agent/memories', payload)
  return res.data
}

export async function getAgentMemory(name) {
  const encoded = encodeURIComponent(name)
  const res = await request.get(`/agent/memories/${encoded}`)
  return res.data
}

export async function updateAgentMemory(name, payload) {
  const encoded = encodeURIComponent(name)
  const res = await request.patch(`/agent/memories/${encoded}`, payload)
  return res.data
}

export async function deleteAgentMemory(name) {
  const encoded = encodeURIComponent(name)
  const res = await request.delete(`/agent/memories/${encoded}`)
  return res.data
}

export async function fetchDeliverable(relPath) {
  const encoded = String(relPath || '')
    .split('/')
    .map((seg) => encodeURIComponent(seg))
    .join('/')
  const res = await request.get(`/agent/deliverables/${encoded}`)
  return res.data
}

export function deliverableDownloadUrl(relPath) {
  const base = import.meta.env.VUE_APP_API_BASE_URL ?? '/api'
  const encoded = String(relPath || '')
    .split('/')
    .map((seg) => encodeURIComponent(seg))
    .join('/')
  const root = base.endsWith('/') ? base.slice(0, -1) : base
  return `${root}/agent/deliverables/${encoded}/download`
}

export async function resolveAgentApproval(approvalId, decision, remember = false) {
  const res = await request.post(`/agent/approvals/${approvalId}`, {
    decision,
    remember,
  })
  return res.data
}

export async function pollAgentJob(jobId, { onApproval, onProgress, shouldAbort } = {}) {
  const started = Date.now()
  let pendingApprovalId = null
  let lastProgressKey = ''
  while (Date.now() - started < JOB_TIMEOUT_MS) {
    if (shouldAbort?.()) {
      throw new JobAbortedError()
    }
    const job = await getAgentJob(jobId)
    if (onProgress && job.progress) {
      const p = job.progress
      const progressKey = JSON.stringify({
        steps: (p.tool_steps || []).length,
        running: p.running_tool?.tool || null,
        phase: p.phase,
        thinking: p.thinking || '',
        answer: p.answer || '',
        todo: p.todo_items || [],
        skills: p.loaded_skills || [],
        reports: p.report_links || [],
        memories: p.memory_saved || [],
      })
      if (progressKey !== lastProgressKey) {
        lastProgressKey = progressKey
        onProgress(job)
      }
    }
    if (job.status === 'awaiting_approval' && job.approval) {
      const approvalId = job.approval.id
      if (approvalId !== pendingApprovalId && onApproval) {
        pendingApprovalId = approvalId
        await onApproval(job.approval)
      }
    }
    if (job.status === 'completed') {
      return job.result
    }
    if (job.status === 'cancelled') {
      throw new JobAbortedError()
    }
    if (job.status === 'failed') {
      throw new Error(job.error || 'Agent job failed')
    }
    await sleep(job.progress?.running_tool ? JOB_POLL_MS_FAST : JOB_POLL_MS)
  }
  throw new Error('Agent 响应超时，请稍后重试')
}

async function mockStreamResponse(content, onProgress) {
  const steps = [
    { tool: 'query_data', params: { resource: 'submit_record' }, summary: '返回 96 行', status: 'ok' },
    { tool: 'aggregate_data', params: { op: 'count' }, summary: 'aggregate_data 返回 1 行', status: 'ok' },
  ]
  const accumulated = []
  if (onProgress) {
    onProgress({ progress: { phase: 'llm', hint: '正在调用模型…', tool_steps: [], running_tool: null, answer: '' } })
    await sleep(600)
    for (const step of steps) {
      onProgress({
        progress: {
          phase: 'tools',
          hint: `正在执行 ${step.tool}…`,
          tool_steps: [...accumulated],
          running_tool: { tool: step.tool, params: step.params },
          answer: '',
        },
      })
      await sleep(500)
      accumulated.push(step)
      onProgress({
        progress: {
          phase: 'tools',
          hint: '工具执行完成…',
          tool_steps: [...accumulated],
          running_tool: null,
          answer: '',
        },
      })
    }
  } else {
    await sleep(MOCK_DELAY_MS)
  }
  return getMockResponse(content)
}

/**
 * 发送消息并等待整轮 Loop 完成（含权限审批轮询）
 */
export async function postAgentMessage(sessionId, content, context = {}, hooks = {}) {
  if (USE_MOCK) {
    if (hooks.shouldAbort) {
      for (let i = 0; i < 8; i++) {
        if (hooks.shouldAbort()) throw new JobAbortedError()
        await sleep(200)
      }
    }
    return mockStreamResponse(content, hooks.onProgress)
  }
  const { job_id: jobId } = await submitAgentMessage(sessionId, content, context)
  if (hooks.onJobStarted) hooks.onJobStarted(jobId)
  return pollAgentJob(jobId, {
    onApproval: hooks.onApproval,
    onProgress: hooks.onProgress,
    shouldAbort: hooks.shouldAbort,
  })
}

/**
 * 兼容旧接口：单次 query（同步阻塞）
 */
export function postAgentQuery(question, context = {}) {
  if (USE_MOCK) {
    return new Promise((resolve) => {
      setTimeout(() => resolve(getMockResponse(question)), MOCK_DELAY_MS)
    })
  }
  return request
    .post('/agent/query', { question, context })
    .then((res) => res.data)
}

export async function bootstrapAgentSession() {
  if (USE_MOCK) {
    return {
      id: 'mock-session',
      title: '演示对话',
      permission_mode: 'analyze',
      messages: [],
      message_count: 0,
    }
  }
  const listed = await listAgentSessions()
  const sessions = listed.sessions || []
  const activeId = listed.active_session_id || (sessions[0] && sessions[0].id)
  if (activeId) {
    return getAgentSession(activeId)
  }
  return createAgentSession({ permission_mode: 'analyze' })
}
