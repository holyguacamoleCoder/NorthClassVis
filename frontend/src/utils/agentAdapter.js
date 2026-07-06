/**
 * Map backend turn result / legacy query response to AgentChatFloat message shape.
 */

import {
  extractVisualLinksFromToolMessages,
  mergeVisualLinks,
  stripVisualLinkMarkdown,
} from '@/utils/visualLinks.js'
import {
  extractReportLinksFromToolMessages,
  mergeReportLinks,
  stripReportLinkMarkdown,
} from '@/utils/reportLinks.js'
import { enrichToolStep, summarizeToolContent } from '@/utils/agentPlanUtils.js'
import { buildTurnTimeline } from '@/utils/agentTimeline.js'

const MODE_LABELS = {
  consult: '咨询',
  analyze: '分析',
  produce: '产出',
}

export function modeLabel(mode) {
  return MODE_LABELS[mode] || mode || '分析'
}

const MEMORY_RESULT_RE =
  /\[Memory (?:saved|updated|removed):\s*([^\]]+)\]/i

function parseMemoryEventFromContent(content) {
  const match = MEMORY_RESULT_RE.exec(content || '')
  if (!match) return null
  const fields = {}
  for (const part of match[1].matchAll(/(\w+)=([^,]+)/g)) {
    fields[part[1]] = part[2].trim()
  }
  return {
    action: fields.action || 'saved',
    label: fields.name || fields.target || 'memory',
    name: fields.name,
    type: fields.type,
    target: fields.target,
    path: fields.path,
  }
}

function extractMemorySavedFromToolMessages(toolMessages) {
  const out = []
  const seen = new Set()
  for (const msg of toolMessages || []) {
    if (msg.name !== 'memory' && msg.name !== 'save_memory') continue
    if (msg.status && msg.status !== 'ok') continue
    const event = parseMemoryEventFromContent(msg.content)
    if (!event) continue
    const key = JSON.stringify(event)
    if (seen.has(key)) continue
    seen.add(key)
    out.push(event)
  }
  return out
}

function stripAnswerMarkdown(answer, visualLinks, reportLinks) {
  const hasLinks = (visualLinks || []).length > 0
  const hasReports = (reportLinks || []).length > 0
  let text = stripVisualLinkMarkdown(answer || '', hasLinks)
  text = stripReportLinkMarkdown(text, hasReports)
  return text
}

function buildAssistantUiFromTurn(turnMsgs) {
  const callParams = {}
  const toolMessages = []
  let firstToolIdx = -1

  for (let i = 0; i < turnMsgs.length; i++) {
    const msg = turnMsgs[i]
    if (msg.role === 'tool' && firstToolIdx < 0) {
      firstToolIdx = i
    }
  }

  let thinking = ''
  const postTexts = []

  for (let i = 0; i < turnMsgs.length; i++) {
    const msg = turnMsgs[i]
    if (msg.role === 'assistant') {
      const text = (msg.content || '').trim()
      const toolCalls = msg.toolCalls || []
      for (const tc of toolCalls) {
        if (tc.id) {
          callParams[tc.id] = {
            name: tc.name,
            params: tc.arguments || {},
          }
        }
      }
      if (!text) continue
      if (firstToolIdx < 0 || i < firstToolIdx) {
        if (!thinking) thinking = text
      } else {
        postTexts.push(text)
      }
      continue
    }
    if (msg.role === 'tool') {
      const info = callParams[msg.toolCallId] || {}
      toolMessages.push({
        name: msg.name || info.name,
        content: msg.content,
        status: msg.status,
        params: info.params || {},
        call_id: msg.toolCallId,
      })
    }
  }

  let answer = ''
  let closing = ''
  if (postTexts.length === 1) {
    closing = postTexts[0]
  } else if (postTexts.length > 1) {
    answer = postTexts[0]
    closing = postTexts[postTexts.length - 1]
  }

  const visual_links = extractVisualLinksFromToolMessages(toolMessages)
  const report_links = extractReportLinksFromToolMessages(toolMessages)
  const memory_saved = extractMemorySavedFromToolMessages(toolMessages)
  const timeline = buildTurnTimeline(turnMsgs)

  return {
    role: 'assistant',
    thinking: thinking.trim(),
    answer: stripAnswerMarkdown(answer, visual_links, report_links),
    closing: stripAnswerMarkdown(closing, visual_links, report_links),
    evidence: [],
    report_evidence: [],
    actions: [],
    visual_links,
    report_links,
    memory_saved,
    trace: { steps: toolMessages.map(toolMsgToStep) },
    timeline,
    goal_check: null,
    summary: null,
    revealPhase: 5,
    isHistory: true,
  }
}

export function legacyToAssistantMessage(res) {
  const visual_links = mergeVisualLinks(res.visual_links || [], [])
  const report_links = mergeReportLinks(res.report_links || [], [])
  const memory_saved = Array.isArray(res.memory_saved) ? res.memory_saved : []
  const hasLinks = visual_links.length > 0
  const hasReports = report_links.length > 0
  const actions = (res.actions || []).filter((a) => {
    const text = String(a)
    if (hasLinks && /点击下方图表入口/.test(text)) return false
    if (hasReports && /预览.*导出/.test(text)) return false
    return true
  })
  const answer = stripAnswerMarkdown(res.answer || '', visual_links, report_links)
  const closing = stripAnswerMarkdown(res.closing || '', visual_links, report_links)
  return {
    role: 'assistant',
    thinking: (res.thinking || '').trim(),
    thinking_updates: Array.isArray(res.thinking_updates)
      ? res.thinking_updates.map((t) => String(t || '').trim()).filter(Boolean)
      : [],
    answer,
    closing,
    evidence: res.evidence || [],
    report_evidence: Array.isArray(res.report_evidence) ? res.report_evidence : [],
    report_final_check: res.report_final_check || null,
    actions,
    visual_links,
    report_links,
    memory_saved,
    trace: res.trace || null,
    timeline: Array.isArray(res.timeline) ? res.timeline : [],
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
      closing: '',
      evidence: [],
      report_evidence: [],
      actions: [],
      visual_links: [],
      report_links: [],
      trace: { steps: [] },
    })
  }
  return legacyToAssistantMessage(result)
}

export function stripRunModifyBlock(text) {
  let out = String(text || '')
  out = out.replace(/\[run_modify\][\s\S]*?\[\/run_modify\]\s*/g, '')
  out = out.replace(/^这是对上一轮数据计算的修改：[\s\S]*?(?:\n\n|$)/, '')
  return out.trim()
}

export function userMessage(text) {
  return { role: 'user', text: stripRunModifyBlock(text) }
}

export function sessionMessagesToUi(messages) {
  if (!Array.isArray(messages)) return []
  const ui = []
  let turn = []

  const flushTurn = () => {
    if (!turn.length) return
    const firstUser = turn.find((m) => m.role === 'user')
    if (firstUser) ui.push(userMessage(firstUser.content))
    const rest = turn.filter((m) => m.role !== 'user')
    if (rest.length) {
      const assistant = buildAssistantUiFromTurn(rest)
      if (
        assistant.thinking ||
        assistant.answer ||
        assistant.closing ||
        (assistant.trace?.steps?.length)
      ) {
        ui.push(assistant)
      }
    }
    turn = []
  }

  for (const msg of messages) {
    if (msg.role === 'user') {
      flushTurn()
      turn = [msg]
      continue
    }
    turn.push(msg)
  }
  flushTurn()

  return ui.filter(
    (m) =>
      m.role === 'user' ||
      (m.trace && m.trace.steps && m.trace.steps.length) ||
      (m.timeline && m.timeline.length) ||
      (m.thinking && m.thinking.trim()) ||
      (m.answer && m.answer.trim()) ||
      (m.closing && m.closing.trim()),
  )
}

function enrichStepWithRun(step, run) {
  if (!run || !step) return step
  const terminal = run.status === 'superseded' || run.status === 'cancelled'
  return {
    ...step,
    run_id: run.run_id,
    parent_run_id: run.parent_run_id || step.parent_run_id,
    patch: run.patch || step.patch,
    derive_strategy: run.derive_strategy || step.derive_strategy,
    run_status: run.status,
    status: terminal ? run.status : step.status,
  }
}

/** Attach persisted run registry metadata when reloading a session. */
export function enrichUiMessagesWithRuns(messages, runs) {
  if (!Array.isArray(messages) || !Array.isArray(runs) || !runs.length) {
    return messages
  }
  const byCall = new Map()
  const dataRuns = []
  for (const run of runs) {
    if (run.tool_call_id) byCall.set(String(run.tool_call_id), run)
    if (run.tool_name === 'query_data' || run.tool_name === 'aggregate_data') {
      dataRuns.push(run)
    }
  }
  let dataIdx = 0

  const pickRun = (step) => {
    const callId = step?.call_id
    if (callId && byCall.has(String(callId))) {
      return byCall.get(String(callId))
    }
    if (step?.tool !== 'query_data' && step?.tool !== 'aggregate_data') return null
    while (dataIdx < dataRuns.length) {
      const candidate = dataRuns[dataIdx]
      dataIdx += 1
      if (candidate.tool_name === step.tool) return candidate
    }
    return null
  }

  const enrichStep = (step) => enrichStepWithRun(step, pickRun(step))

  return messages.map((msg) => {
    if (msg.role !== 'assistant') return msg
    dataIdx = 0
    const traceSteps = (msg.trace?.steps || []).map(enrichStep)
    const timeline = (msg.timeline || []).map((item) => {
      if (item.kind !== 'tool' || !item.step) return item
      return { ...item, step: enrichStep(item.step) }
    })
    return {
      ...msg,
      trace: traceSteps.length ? { steps: traceSteps } : msg.trace,
      timeline: timeline.length ? timeline : msg.timeline,
    }
  })
}

function toolMsgToStep(msg) {
  return enrichToolStep({
    tool: msg.name || 'unknown',
    params: msg.params || {},
    summary: summarizeToolContent(msg.name, msg.content),
    status: msg.status || 'ok',
    error: msg.status !== 'ok' ? msg.content : '',
    call_id: msg.call_id,
  })
}

export const RECOVERY_HINTS = {
  consult_list_loop_guard: '当前为咨询模式，请切换到「分析」模式后重试。',
  todo_only_loop_guard: 'Agent 仅更新了计划但未完成数据分析，请继续等待或补充问题。',
  tool_loop_guard: '工具调用陷入循环，请换一种问法。',
  tool_error_loop_guard: '工具连续报错，请检查分析范围或权限模式。',
  report_incomplete_guard:
    '报告未写入成功，请勿把聊天摘要当正式报告；可让我先 read_file 再按章节补写，或新建会话用真实学号重来。',
  max_turn_limit:
    '本轮 Agent 轮次已达上限并已自动停止；报告草稿可先预览，或发送「继续补全」接着写。',
  report_validate_loop_guard:
    '报告同一校验错误反复出现，已停止空转；请先预览或 read_file 后再说明要改哪一节。',
  report_polish_loop_guard:
    '报告已基本可交付（仅剩提醒项），无需继续反复修补；可直接预览。',
  context_overflow_exhausted: '对话上下文过长，请新建会话或简化问题。',
  transient_error_exhausted: '网络或限流导致重试失败，请稍后再试。',
  llm_no_response: 'LLM 无响应，请稍后重试。',
}

export function createStreamingAssistantMessage() {
  return {
    role: 'assistant',
    thinking: '',
    thinking_updates: [],
    answer: '',
    closing: '',
    evidence: [],
    report_evidence: [],
    actions: [],
    visual_links: [],
    report_links: [],
    memory_saved: [],
    trace: { steps: [] },
    timeline: [],
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
  const steps = (Array.isArray(progress.tool_steps) ? progress.tool_steps : []).map(
    (s) => enrichToolStep(s),
  )
  if (progress.running_tool) {
    const rt = progress.running_tool
    const tool = rt.tool || 'tool'
    steps.push(
      enrichToolStep({
        call_id: rt.call_id,
        run_id: rt.run_id,
        parent_run_id: rt.parent_run_id,
        patch: rt.patch,
        derive_strategy: rt.derive_strategy,
        tool,
        params: rt.params || {},
        summary: tool === 'todo_write' ? '更新计划中…' : tool === 'load_skill' ? '加载技能中…' : '执行中…',
        status: 'running',
        run_status: 'executing',
      }),
    )
  }
  return steps
}

/** Sync session-level todo / skills from job progress while streaming. */
export function applyJobSessionMeta(ctx, progress) {
  if (!ctx || !progress) return
  if (Array.isArray(progress.todo_items)) {
    ctx.todoItems = progress.todo_items
  }
  if (Array.isArray(progress.loaded_skills)) {
    ctx.loadedSkills = progress.loaded_skills
  }
}

export function applyProgressToMessage(msg, job) {
  const progress = job?.progress
  if (!msg || !progress) return
  msg.statusHint = progress.hint || msg.statusHint
  msg.trace = { steps: progressToTraceSteps(progress) }
  if (Array.isArray(progress.timeline)) {
    msg.timeline = progress.timeline.map((item) =>
      item.kind === 'tool' && item.step ? { ...item, step: enrichToolStep(item.step) } : item,
    )
  }
  msg._runningTool = progress.running_tool || null
  if (Array.isArray(progress.thinking_updates) && progress.thinking_updates.length) {
    msg.thinking_updates = progress.thinking_updates.map((t) => String(t || '').trim()).filter(Boolean)
  }
  if (progress.thinking !== undefined && progress.thinking !== null && progress.thinking !== '') {
    if (!msg.thinking || !String(msg.thinking).trim()) {
      msg.thinking = progress.thinking
    }
  }
  if (progress.answer !== undefined && progress.answer !== null && progress.answer !== '') {
    msg.answer = progress.answer
  }
  if (progress.closing !== undefined && progress.closing !== null && progress.closing !== '') {
    msg.closing = progress.closing
  }
  if (Array.isArray(progress.report_links) && progress.report_links.length) {
    msg.report_links = mergeReportLinks(msg.report_links, progress.report_links)
  }
  if (Array.isArray(progress.memory_saved) && progress.memory_saved.length) {
    msg.memory_saved = progress.memory_saved
  }
}

export function mergeRunMetaIntoPayload(payload, priorMsg) {
  if (!payload || !priorMsg) return payload
  const priorSteps = [
    ...(priorMsg.trace?.steps || []),
    ...(priorMsg.timeline || [])
      .filter((item) => item.kind === 'tool' && item.step)
      .map((item) => item.step),
  ]
  const metaByCall = new Map()
  for (const step of priorSteps) {
    if (step?.call_id && step?.run_id) {
      metaByCall.set(step.call_id, step)
    }
  }
  if (!metaByCall.size) return payload

  const copy = { ...payload }
  if (copy.trace?.steps) {
    copy.trace = {
      steps: copy.trace.steps.map((step) => mergeStepRunMeta(step, metaByCall)),
    }
  }
  if (Array.isArray(copy.timeline)) {
    copy.timeline = copy.timeline.map((item) => {
      if (item.kind !== 'tool' || !item.step) return item
      return { ...item, step: mergeStepRunMeta(item.step, metaByCall) }
    })
  }
  return copy
}

function mergeStepRunMeta(step, metaByCall) {
  const prior = metaByCall.get(step?.call_id)
  if (!prior) return step
  return {
    ...step,
    run_id: step.run_id || prior.run_id,
    parent_run_id: step.parent_run_id || prior.parent_run_id,
    patch: step.patch || prior.patch,
    derive_strategy: step.derive_strategy || prior.derive_strategy,
    run_status: step.run_status || prior.run_status,
  }
}

export function recoveryHint(reason) {
  return RECOVERY_HINTS[reason] || ''
}
