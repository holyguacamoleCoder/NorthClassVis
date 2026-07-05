/**
 * Build interleaved turn timeline from serialized session messages (mirrors backend adapter).
 */

import { enrichToolStep, summarizeToolContent } from '@/utils/agentPlanUtils.js'

function toolMsgToStep(msg) {
  return enrichToolStep({
    tool: msg.name || 'unknown',
    params: msg.params || {},
    summary: summarizeToolContent(msg.name, msg.content),
    status: msg.status || 'ok',
    error: msg.status !== 'ok' ? msg.content : '',
    call_id: msg.call_id,
    raw_content: msg.content,
  })
}

function firstToolIndex(turnMsgs) {
  for (let i = 0; i < turnMsgs.length; i++) {
    if (turnMsgs[i].role === 'tool') return i
  }
  return -1
}

/** @returns {Array<{kind:string, phase:string, text?:string, step?:object}>} */
export function buildTurnTimeline(turnMsgs) {
  if (!Array.isArray(turnMsgs) || !turnMsgs.length) return []

  const callParams = {}
  for (const msg of turnMsgs) {
    if (msg.role !== 'assistant') continue
    for (const tc of msg.toolCalls || []) {
      if (tc.id) {
        callParams[tc.id] = { name: tc.name, params: tc.arguments || {} }
      }
    }
  }

  const firstTool = firstToolIndex(turnMsgs)
  const timeline = []

  turnMsgs.forEach((msg, idx) => {
    if (msg.role === 'assistant') {
      const text = String(msg.content || '').trim()
      if (!text) return
      const hasTools = (msg.toolCalls || []).length > 0
      if (firstTool >= 0 && idx < firstTool) {
        timeline.push({ kind: 'narration', phase: 'plan', text })
      } else if (hasTools) {
        timeline.push({ kind: 'narration', phase: 'process', text })
      } else {
        timeline.push({ kind: 'narration', phase: 'conclusion', text })
      }
      return
    }
    if (msg.role === 'tool') {
      const info = callParams[msg.toolCallId] || {}
      timeline.push({
        kind: 'tool',
        phase: 'process',
        step: toolMsgToStep({
          name: msg.name || info.name,
          content: msg.content,
          status: msg.status,
          params: info.params || {},
          call_id: msg.toolCallId,
        }),
      })
    }
  })

  return timeline
}

/** Process section: narration between tools + tool steps (excludes plan/conclusion). */
export function processTimelineItems(msg) {
  const tl = msg?.timeline
  if (Array.isArray(tl) && tl.length) {
    return tl.filter((item) => item.kind === 'tool' || item.phase === 'process')
  }
  const steps = msg?.trace?.steps || []
  return steps.map((step) => ({ kind: 'tool', phase: 'process', step }))
}

export function processTimelineStats(items) {
  const list = items || []
  const tools = list.filter((i) => i.kind === 'tool')
  const failed = tools.filter((i) => ['fail', 'denied', 'blocked'].includes(i.step?.status))
  return { total: tools.length, failed: failed.length }
}

const DATA_RUN_TOOLS = new Set(['query_data', 'aggregate_data'])

export function isModifiableRunStep(step) {
  if (!step?.run_id) return false
  if (step.status === 'running') return false
  if (['superseded', 'cancelled'].includes(step.status)) return false
  if (['superseded', 'cancelled'].includes(step.run_status)) return false
  return DATA_RUN_TOOLS.has(step.tool)
}

/** One modify entry per turn: prefer latest aggregate, else latest query. */
export function pickPrimaryModifyRun(steps) {
  const list = (steps || []).filter(isModifiableRunStep)
  if (!list.length) return null
  for (let i = list.length - 1; i >= 0; i -= 1) {
    if (list[i].tool === 'aggregate_data') return list[i]
  }
  return list[list.length - 1]
}
