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
        timeline.push({ kind: 'narration', phase: 'plan_update', text })
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

/**
 * @typedef {object} StepGroup
 * @property {string} id
 * @property {'plan'|'plan_update'|'process'} phase
 * @property {number} [updateIndex]
 * @property {string} text
 * @property {Array<{kind:string, phase:string, text?:string, step?:object}>} tools
 */

/** Split interleaved timeline into plan / plan_update step groups with nested tools. */
export function groupTimelineIntoSteps(timeline) {
  if (!Array.isArray(timeline) || !timeline.length) return []

  /** @type {StepGroup[]} */
  const groups = []
  /** @type {StepGroup|null} */
  let current = null
  let updateIndex = 0

  const pushCurrent = () => {
    if (!current) return
    groups.push(current)
    current = null
  }

  const startGroup = (phase, text) => {
    pushCurrent()
    if (phase === 'plan') {
      current = { id: 'plan', phase: 'plan', text: text || '', tools: [] }
      return
    }
    updateIndex += 1
    current = {
      id: `update-${updateIndex}`,
      phase: 'plan_update',
      updateIndex,
      text: text || '',
      tools: [],
    }
  }

  const ensureGroup = () => {
    if (!current) {
      current = { id: 'plan', phase: 'plan', text: '', tools: [] }
    }
  }

  for (const item of timeline) {
    if (item.kind === 'narration') {
      if (item.phase === 'plan') {
        startGroup('plan', String(item.text || '').trim())
      } else if (item.phase === 'plan_update') {
        startGroup('plan_update', String(item.text || '').trim())
      } else if (item.phase === 'conclusion') {
        pushCurrent()
      }
      continue
    }
    if (item.kind === 'tool' || item.phase === 'process') {
      ensureGroup()
      current.tools.push(item)
    }
  }

  pushCurrent()
  return groups
}

/** Label for a step group header. */
export function stepGroupLabel(group, ui) {
  if (!group) return ''
  if (group.phase === 'plan') return ui.sectionPlan
  if (group.phase === 'plan_update') return ui.sectionPlanUpdate(group.updateIndex || 1)
  return ui.sectionProcess
}

/** Affiliation badge on tool bubbles (plan / plan_update). */
export function stepGroupAffiliationLabel(group, ui) {
  if (!group || group.phase === 'process') return ''
  return stepGroupLabel(group, ui)
}

export function stepGroupStats(group) {
  const tools = group?.tools || []
  const failed = tools.filter((i) =>
    ['fail', 'denied', 'blocked'].includes(i.step?.status)
  )
  return { total: tools.length, failed: failed.length }
}

/** Whether message has interleaved timeline suitable for step grouping. */
export function hasInterleavedTimeline(msg) {
  const tl = msg?.timeline
  if (!Array.isArray(tl) || !tl.length) return false
  const hasPlanNarration = tl.some(
    (item) => item.kind === 'narration' && (item.phase === 'plan' || item.phase === 'plan_update')
  )
  const hasTools = tl.some((item) => item.kind === 'tool')
  return hasPlanNarration || hasTools
}

/** Build step groups from timeline, or synthesize from legacy fields. */
export function buildStepGroupsFromMessage(msg) {
  const tl = msg?.timeline
  if (Array.isArray(tl) && tl.length) {
    const groups = enrichStepGroupText(groupTimelineIntoSteps(tl), msg)
    if (groups.length) return groups
  }
  return buildLegacyStepGroups(msg)
}

function enrichStepGroupText(groups, msg) {
  if (!groups.length) return groups
  return groups.map((g) => {
    if (g.phase === 'plan' && !g.text.trim() && msg?.thinking) {
      return { ...g, text: String(msg.thinking).trim() }
    }
    return g
  })
}

function buildLegacyStepGroups(msg) {
  /** @type {StepGroup[]} */
  const groups = []
  const thinking = String(msg?.thinking || '').trim()
  if (thinking) {
    groups.push({ id: 'plan', phase: 'plan', text: thinking, tools: [] })
  }

  const updates = Array.isArray(msg?.thinking_updates) ? msg.thinking_updates : []
  updates.forEach((raw, i) => {
    const text = String(raw || '').trim()
    if (!text) return
    groups.push({
      id: `update-${i + 1}`,
      phase: 'plan_update',
      updateIndex: i + 1,
      text,
      tools: [],
    })
  })

  const steps = msg?.trace?.steps || []
  const toolItems = steps.map((step) => ({ kind: 'tool', phase: 'process', step }))
  if (toolItems.length) {
    if (groups.length) {
      const last = groups[groups.length - 1]
      groups[groups.length - 1] = { ...last, tools: [...last.tools, ...toolItems] }
    } else {
      groups.push({ id: 'process', phase: 'process', text: '', tools: toolItems })
    }
  }

  return groups
}

/** Default expand: plan + latest group; also expand groups with failures or while streaming. */
export function stepGroupDefaultExpanded(group, index, groups, msg) {
  const isLast = index === groups.length - 1
  if (msg?.streaming && isLast) return true
  if (group.phase === 'plan') return true
  const { failed } = stepGroupStats(group)
  if (failed > 0) return true
  return isLast
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
