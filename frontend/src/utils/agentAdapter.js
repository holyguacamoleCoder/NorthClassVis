/**
 * Map backend turn result / legacy query response to AgentChatFloat message shape.
 */

import {
  extractVisualLinksFromToolMessages,
  mergeVisualLinks,
  stripVisualLinkMarkdown,
} from '@/utils/visualLinks.js'

const MODE_LABELS = {
  consult: '咨询',
  analyze: '分析',
  produce: '产出',
}

export function modeLabel(mode) {
  return MODE_LABELS[mode] || mode || '分析'
}

export function legacyToAssistantMessage(res) {
  const visual_links = mergeVisualLinks(res.visual_links || [], [])
  const hasLinks = visual_links.length > 0
  const actions = (res.actions || []).filter(
    (a) => !hasLinks || !/点击下方图表入口/.test(String(a)),
  )
  return {
    role: 'assistant',
    answer: stripVisualLinkMarkdown(res.answer || '', hasLinks),
    evidence: res.evidence || [],
    actions,
    visual_links,
    trace: res.trace || null,
    goal_check: res.goal_check || null,
    summary: res.summary || null,
    continue_reason: res.continue_reason || null,
    revealPhase: 0,
  }
}

export function turnResultToAssistantMessage(result) {
  if (!result) {
    return legacyToAssistantMessage({
      answer: '未收到 Agent 响应。',
      evidence: [],
      actions: [],
      visual_links: [],
      trace: { steps: [] },
    })
  }
  return legacyToAssistantMessage(result)
}

export function userMessage(text) {
  return { role: 'user', text: String(text || '') }
}

export function sessionMessagesToUi(messages) {
  if (!Array.isArray(messages)) return []
  const ui = []
  let pendingTools = []
  const callParams = {}

  const flushAssistant = (content) => {
    if (pendingTools.length) {
      const visual_links = extractVisualLinksFromToolMessages(pendingTools)
      const hasLinks = visual_links.length > 0
      ui.push({
        role: 'assistant',
        answer: stripVisualLinkMarkdown(content || '', hasLinks),
        evidence: [],
        actions: [],
        visual_links,
        trace: { steps: pendingTools.map(toolMsgToStep) },
        goal_check: null,
        summary: null,
        revealPhase: 5,
        isHistory: true,
      })
      pendingTools = []
      return
    }
    if (content) {
      ui.push({
        role: 'assistant',
        answer: content,
        evidence: [],
        actions: [],
        visual_links: [],
        trace: null,
        goal_check: null,
        summary: null,
        revealPhase: 5,
        isHistory: true,
      })
    }
  }

  for (const msg of messages) {
    if (msg.role === 'user') {
      flushAssistant('')
      ui.push(userMessage(msg.content))
      continue
    }
    if (msg.role === 'assistant') {
      if (msg.toolCalls && msg.toolCalls.length) {
        for (const tc of msg.toolCalls) {
          if (tc.id) {
            callParams[tc.id] = {
              name: tc.name,
              params: tc.arguments || {},
            }
          }
        }
        continue
      }
      flushAssistant(msg.content || '')
      continue
    }
    if (msg.role === 'tool') {
      const info = callParams[msg.toolCallId] || {}
      pendingTools.push({
        name: msg.name || info.name,
        content: msg.content,
        status: msg.status,
        params: info.params || {},
      })
    }
  }
  flushAssistant('')
  return ui.filter(
    (m) =>
      m.role === 'user' ||
      (m.trace && m.trace.steps && m.trace.steps.length) ||
      (m.answer && m.answer.trim()),
  )
}

function toolMsgToStep(msg) {
  return {
    tool: msg.name || 'unknown',
    params: msg.params || {},
    summary: summarizeToolContent(msg.name, msg.content),
    status: msg.status || 'ok',
    error: msg.status !== 'ok' ? msg.content : '',
  }
}

function summarizeToolContent(name, content) {
  const text = String(content || '').trim()
  if (!text) return `${name || 'tool'} 无返回`
  if (text.length > 120) return text.slice(0, 119) + '…'
  return text
}

export const RECOVERY_HINTS = {
  consult_list_loop_guard: '当前为咨询模式，请切换到「分析」模式后重试。',
  todo_only_loop_guard: 'Agent 仅更新了计划但未完成数据分析，请继续等待或补充问题。',
  tool_loop_guard: '工具调用陷入循环，请换一种问法。',
  tool_error_loop_guard: '工具连续报错，请检查分析范围或权限模式。',
  context_overflow_exhausted: '对话上下文过长，请新建会话或简化问题。',
  transient_error_exhausted: '网络或限流导致重试失败，请稍后再试。',
  llm_no_response: 'LLM 无响应，请稍后重试。',
}

export function createStreamingAssistantMessage() {
  return {
    role: 'assistant',
    answer: '',
    evidence: [],
    actions: [],
    visual_links: [],
    trace: { steps: [] },
    goal_check: null,
    summary: null,
    continue_reason: null,
    revealPhase: 0,
    streaming: true,
    statusHint: '思考中…',
  }
}

export function progressToTraceSteps(progress) {
  if (!progress) return []
  const steps = Array.isArray(progress.tool_steps) ? [...progress.tool_steps] : []
  if (progress.running_tool) {
    steps.push({
      call_id: progress.running_tool.call_id,
      tool: progress.running_tool.tool || 'tool',
      params: progress.running_tool.params || {},
      summary: '执行中…',
      status: 'running',
    })
  }
  return steps
}

export function applyProgressToMessage(msg, job) {
  const progress = job?.progress
  if (!msg || !progress) return
  msg.statusHint = progress.hint || msg.statusHint
  msg.trace = { steps: progressToTraceSteps(progress) }
  if (progress.answer !== undefined && progress.answer !== null && progress.answer !== '') {
    msg.answer = progress.answer
  }
}

export function recoveryHint(reason) {
  return RECOVERY_HINTS[reason] || ''
}
