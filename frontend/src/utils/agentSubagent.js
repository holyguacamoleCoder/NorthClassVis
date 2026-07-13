/** Sub-agent step labels and result parsing (mirrors backend subagent/result_parse). */

export const SUBAGENT_KIND_LABELS = {
  data_analyst: '数据侦察',
  report_writer: '报告写作',
  report_reviewer: '报告修订',
}

export function subagentKindLabel(kind) {
  const key = String(kind || '').trim().toLowerCase()
  return SUBAGENT_KIND_LABELS[key] || key || '子 Agent'
}

export function parseSubagentToolResult(content) {
  const text = String(content || '').trim()
  const out = {
    ok: false,
    kind: '',
    turns: 0,
    refs: [],
    datasetIds: [],
    summary: '',
    error: null,
  }
  if (!text) return out

  const header = text.match(/\[SubAgent\s+(\S+)\s+(OK|FAIL)\]/i)
  if (header) {
    out.kind = header[1]
    out.ok = header[2].toUpperCase() === 'OK'
  }

  const turns = text.match(/^turns:\s*(\d+)/m)
  if (turns) out.turns = Number(turns[1]) || 0

  let section = null
  for (const line of text.split('\n')) {
    const stripped = line.trim()
    if (stripped === 'refs:') {
      section = 'refs'
      continue
    }
    if (stripped === 'dataset_ids:') {
      section = 'datasetIds'
      continue
    }
    if (stripped === 'summary:') {
      section = 'summary'
      continue
    }
    if (stripped.startsWith('error:')) {
      out.error = stripped.slice(6).trim()
      section = null
      continue
    }
    if (section === 'refs' && stripped.startsWith('- ')) {
      out.refs.push(stripped.slice(2).trim())
    } else if (section === 'datasetIds' && stripped.startsWith('- ')) {
      out.datasetIds.push(stripped.slice(2).trim())
    } else if (section === 'summary') {
      if (stripped && stripped !== '(empty)') {
        out.summary = out.summary ? `${out.summary}\n${stripped}` : stripped
      }
    }
  }
  return out
}

export function summarizeSubagentStep(step) {
  const sub = step?.subagent || {}
  const kind = sub.kind || step?.params?.kind || ''
  const label = subagentKindLabel(kind)
  if (step?.status === 'running') {
    return `${label} · 执行中…`
  }
  if (sub.summary) {
    const preview = sub.summary.replace(/\s+/g, ' ').slice(0, 80)
    return `${label} · ${preview}${sub.summary.length > 80 ? '…' : ''}`
  }
  const parsed = parseSubagentToolResult(step?.raw_content || step?.summary || '')
  if (parsed.summary) {
    const preview = parsed.summary.replace(/\s+/g, ' ').slice(0, 80)
    return `${label} · ${preview}${parsed.summary.length > 80 ? '…' : ''}`
  }
  if (parsed.turns) return `${label} · ${parsed.turns} 轮`
  return label
}

export function innerToolSummary(inner) {
  const tool = inner?.tool || 'tool'
  if (inner?.summary) return inner.summary
  if (inner?.status === 'running') return '执行中…'
  return tool
}

export function buildRunningSubagentStep(runningTool, runningSubagent) {
  const rt = runningTool || {}
  const sub = runningSubagent || {}
  return enrichSubagentStep({
    call_id: rt.call_id,
    tool: 'run_subagent',
    params: rt.params || {
      kind: sub.kind,
      task: sub.task_preview,
    },
    status: 'running',
    subagent: {
      kind: sub.kind || rt.params?.kind,
      task_preview: sub.task_preview || rt.params?.task,
      inner_steps: Array.isArray(sub.inner_steps) ? sub.inner_steps : [],
      turns: sub.turns || 0,
      status: sub.status || 'running',
    },
    summary: summarizeSubagentStep({
      status: 'running',
      params: rt.params,
      subagent: sub,
    }),
  })
}

export function enrichSubagentStep(step) {
  if (!step || typeof step !== 'object') return step
  const next = { ...step, kind: 'subagent', tool: step.tool || 'run_subagent' }
  if (!next.subagent && next.raw_content) {
    const parsed = parseSubagentToolResult(next.raw_content)
    next.subagent = {
      kind: parsed.kind || next.params?.kind,
      task_preview: next.params?.task,
      turns: parsed.turns,
      refs: parsed.refs,
      dataset_ids: parsed.datasetIds,
      summary: parsed.summary,
      error: parsed.error,
      inner_steps: [],
      status: parsed.ok ? 'ok' : 'fail',
    }
  }
  if (!next.summary || next.summary === 'run_subagent 无返回') {
    next.summary = summarizeSubagentStep(next)
  }
  return next
}
