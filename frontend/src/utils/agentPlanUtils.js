/** Shared helpers for agent todo plan display. */

export function todoIcon(status) {
  if (status === 'completed') return '\u2713'
  if (status === 'in_progress') return '\u25D0'
  return '\u25CB'
}

export function planProgress(items) {
  const list = Array.isArray(items) ? items : []
  const total = list.length
  const completed = list.filter((i) => i.status === 'completed').length
  const inProgress = list.find((i) => i.status === 'in_progress')
  return { total, completed, inProgress }
}

export function planProgressLabel(items) {
  const { total, completed } = planProgress(items)
  if (!total) return ''
  return `${completed}/${total}`
}

export function todoItemsFromStep(step) {
  if (!step) return []
  const snap = step.todo_snapshot
  if (snap && Array.isArray(snap.items)) return snap.items
  const params = step.params || {}
  if (!Array.isArray(params.items)) return []
  return params.items.map((raw) => ({
    content: String(raw.content || '').trim(),
    status: String(raw.status || 'pending').toLowerCase(),
    active_form: raw.active_form ? String(raw.active_form).trim() : '',
    acceptance: raw.acceptance ? String(raw.acceptance).trim() : '',
  })).filter((i) => i.content)
}

export function skillNameFromStep(step) {
  if (!step) return ''
  if (step.skill_name) return String(step.skill_name).trim()
  const params = step.params || {}
  return String(params.name || params.skill_name || params.skill || '').trim()
}

export function summarizeToolContent(name, content) {
  const text = String(content || '').trim()
  const tool = name || 'tool'
  if (!text) return `${tool} 无返回`
  if (text.startsWith('Error:')) {
    return summarizeToolError(text)
  }
  if (tool === 'write_file' || tool === 'edit_file') {
    if (text.includes('[Report validate]')) {
      if (text.includes('status: ERRORS') || text.includes('\n  error:')) {
        return '报告校验未通过，需修改后重试'
      }
      if (text.includes('status: OK with warnings')) {
        return '报告已写入（有校验警告）'
      }
      if (text.includes('[Report validate: OK]')) {
        return '报告已写入并通过校验'
      }
    }
    const m = text.match(/\[(?:Write|Edit)\s+OK:\s*path=([^,\]]+)/i)
    if (m) return `${tool === 'write_file' ? '已写入' : '已修改'} ${m[1].trim()}`
  }
  if (tool === 'todo_write') {
    const m = text.match(/\[Plan updated:\s*(\d+)\/(\d+)\s+completed\]/)
    if (m) return `计划 ${m[1]}/${m[2]} 已完成`
    if (text.startsWith('[Plan updated: empty]')) return '计划已清空'
  }
  if (tool === 'load_skill') {
    const loaded = text.match(/\[Skill loaded:\s*([^\]]+)\]/)
    if (loaded) return `已加载技能 ${loaded[1].trim()}`
    if (/already loaded/i.test(text)) return '技能已在本会话加载'
  }
  if (tool === 'query_data' || tool === 'aggregate_data' || tool === 'inspect_schema') {
    try {
      const payload = JSON.parse(text)
      const meta = payload.meta || {}
      const resource = payload.resource || meta.resource || ''
      const rows = payload.rows || []
      const prefix = resource ? `${resource} · ` : ''
      if (tool === 'inspect_schema') {
        const cols = payload.columns || []
        return `${prefix}${cols.length} 列 · ${payload.row_count_estimate || 0} 行`
      }
      const truncated = meta.truncated ? '（已截断）' : ''
      return `${prefix}返回 ${rows.length} 行${truncated}`
    } catch (e) {
      /* fall through */
    }
  }
  if (text.length > 120) return text.slice(0, 119) + '…'
  return text
}

export function summarizeToolError(text) {
  let body = String(text || '').trim()
  if (body.startsWith('Error:')) body = body.slice(6).trim()
  for (const sep of ['\n', ' | Next:', ' | Example:']) {
    const idx = body.indexOf(sep)
    if (idx >= 0) body = body.slice(0, idx).trim()
  }
  body = body.replace(/\s+/g, ' ')
  if (body.length > 120) return body.slice(0, 119) + '…'
  return body || '执行失败'
}

export function dataResourceFromStep(step) {
  if (!step) return ''
  if (step.resource) return String(step.resource)
  const params = step.params || {}
  return String(params.resource || '').trim()
}

export function enrichToolStep(step) {
  if (!step || typeof step !== 'object') return step
  const tool = step.tool || ''
  const next = { ...step }
  if (tool === 'todo_write') {
    const items = todoItemsFromStep(next)
    if (items.length) {
      const completed = items.filter((i) => i.status === 'completed').length
      next.kind = 'todo'
      next.todo_snapshot = { items, completed, total: items.length }
      if (next.status === 'ok') {
        next.summary = `计划 ${completed}/${items.length} 已完成`
      }
    }
  } else if (tool === 'load_skill') {
    const skillName = skillNameFromStep(next)
    if (skillName) {
      next.kind = 'skill'
      next.skill_name = skillName
      if (next.status === 'ok') {
        const summary = String(next.summary || '')
        next.summary = /already loaded/i.test(summary)
          ? `技能 ${skillName} 已在本会话加载`
          : `已加载技能 ${skillName}`
      }
    }
  } else if (tool === 'query_data' || tool === 'aggregate_data' || tool === 'inspect_schema') {
    const resource = dataResourceFromStep(next)
    if (resource) {
      next.kind = 'data'
      next.resource = resource
    }
    if (step.run_id) next.run_id = step.run_id
    if (step.parent_run_id) next.parent_run_id = step.parent_run_id
    if (step.patch && Object.keys(step.patch).length) next.patch = step.patch
    if (step.derive_strategy) next.derive_strategy = step.derive_strategy
    if (step.run_status) next.run_status = step.run_status
    if (['fail', 'denied', 'blocked'].includes(next.status)) {
      next.summary = summarizeToolError(next.error || next.summary || '')
    }
  } else if (tool === 'write_file' || tool === 'edit_file') {
    const content = String(next.raw_content || next.summary || '')
    if (content.includes('[Report validate]')) {
      next.kind = 'report'
      if (content.includes('status: ERRORS') || content.includes('\n  error:')) {
        next.status = 'fail'
        next.summary = '报告校验未通过'
      } else if (content.includes('[Report validate: OK]')) {
        next.summary = '报告已写入并通过校验'
      } else if (content.includes('status: OK with warnings')) {
        next.summary = '报告已写入（有警告）'
      }
    }
  }
  return next
}
