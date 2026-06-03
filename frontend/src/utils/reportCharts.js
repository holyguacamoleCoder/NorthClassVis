/** 解析报告 Markdown 中的 ```report-chart``` 块，预览时复用仪表盘 Vue 图表 */

const CHART_FENCE_RE = /```(?:report-chart|chart|json)\s*\r?\n([\s\S]*?)```/gi

const GENERIC_FENCE_RE = /```\s*\r?\n([\s\S]*?)```/gi

export const REPORT_CHART_LABELS = {
  WeekView: '周视图（选中学生周次）',
  QuestionView: '题目视图（知识点/题目）',
  ScatterView: '散点视图（学生分布）',
  PortraitView: '画像视图（聚类雷达）',
  StudentView: '学生视图',
}

export function isChartPayloadText(raw) {
  try {
    const obj = JSON.parse(String(raw || '').trim())
    const view = obj?.view || obj?.panel
    return typeof view === 'string' && /View$/i.test(view)
  } catch {
    return false
  }
}

export function parseChartBlock(raw) {
  try {
    const obj = JSON.parse(String(raw || '').trim())
    const view = obj.view || obj.panel
    if (!view) return { view: null, params: {}, error: '缺少 view 字段' }
    return {
      view: String(view),
      params: obj.params && typeof obj.params === 'object' ? obj.params : {},
      error: null,
    }
  } catch {
    return { view: null, params: {}, error: '图表块 JSON 无效' }
  }
}

function pushChartSegment(segments, raw) {
  const parsed = parseChartBlock(raw)
  segments.push({
    type: 'chart',
    view: parsed.view,
    params: parsed.params,
    error: parsed.error,
  })
}

function extractChartFences(text) {
  const spans = []
  const re = new RegExp(CHART_FENCE_RE.source, 'gi')
  let m
  while ((m = re.exec(text)) !== null) {
    const body = m[1]
    if (isChartPayloadText(body)) {
      spans.push({ start: m.index, end: m.index + m[0].length, body })
    }
  }
  const generic = new RegExp(GENERIC_FENCE_RE.source, 'gi')
  while ((m = generic.exec(text)) !== null) {
    const body = m[1]
    if (!isChartPayloadText(body)) continue
    const overlaps = spans.some((s) => m.index >= s.start && m.index < s.end)
    if (!overlaps) {
      spans.push({ start: m.index, end: m.index + m[0].length, body })
    }
  }
  spans.sort((a, b) => a.start - b.start)
  return spans
}

/** @returns {{ type: 'md'|'chart', content?: string, view?: string, params?: object, error?: string }[]} */
export function splitReportMarkdown(source) {
  const text = String(source || '')
  if (!text.trim()) return [{ type: 'md', content: '' }]

  const segments = []
  let lastIndex = 0
  const spans = extractChartFences(text)
  for (const span of spans) {
    if (span.start > lastIndex) {
      segments.push({ type: 'md', content: text.slice(lastIndex, span.start) })
    }
    pushChartSegment(segments, span.body)
    lastIndex = span.end
  }
  if (lastIndex < text.length) {
    segments.push({ type: 'md', content: text.slice(lastIndex) })
  }
  if (!segments.length) {
    segments.push({ type: 'md', content: text })
  }
  return segments
}

export function coerceWeekRange(value) {
  if (value == null) return null
  if (Array.isArray(value) && value.length >= 2) {
    const start = Number(value[0])
    const end = Number(value[1])
    if (!Number.isNaN(start) && !Number.isNaN(end)) return [start, end]
  }
  return null
}

function studentIdsFromParams(params) {
  if (!Array.isArray(params?.student_ids)) return []
  return params.student_ids.map(String).filter(Boolean)
}

/** title_ID 形如 Question_xxx；短码多为 knowledge */
export function looksLikeTitleId(id) {
  const s = String(id || '').trim()
  return s.length > 0 && /^Question_/i.test(s)
}

/**
 * 规范化 QuestionView report-chart 参数：title_ids 无匹配时回退为 knowledge 列表。
 * @returns {{ params: object, note?: string }}
 */
export function normalizeQuestionViewParams(params = {}, knowledgeCatalog = []) {
  const out = { ...(params || {}) }
  const catalog = new Set((knowledgeCatalog || []).map(String))
  const rawIds = Array.isArray(out.title_ids)
    ? out.title_ids.map((id) => String(id).trim()).filter(Boolean)
    : []

  if (!rawIds.length) {
    return { params: out }
  }

  const titleLike = rawIds.filter(looksLikeTitleId)
  const shortCodes = rawIds.filter((id) => !looksLikeTitleId(id))

  if (titleLike.length) {
    out.title_ids = titleLike
    if (shortCodes.length && catalog.size) {
      const asKnowledge = shortCodes.filter((k) => catalog.has(k))
      if (asKnowledge.length === 1) {
        out.knowledge = asKnowledge[0]
      } else if (asKnowledge.length > 1) {
        out.knowledge_ids = asKnowledge
      }
    }
    return { params: out }
  }

  if (shortCodes.length && catalog.size) {
    const matched = shortCodes.filter((k) => catalog.has(k))
    if (matched.length) {
      const next = { ...out }
      delete next.title_ids
      if (matched.length === 1) {
        next.knowledge = matched[0]
      } else {
        next.knowledge_ids = matched
      }
      return {
        params: next,
        note:
          'report-chart 中的短码已按知识点解析（非 title_ID）；正文请写「知识点」勿写「题目 ID」。',
      }
    }
  }

  return { params: out }
}

/**
 * 嵌入图表前同步 vuex（周次、选中学生）。
 * @returns {{ ok: boolean, error?: string }}
 */
export async function ensureReportChartContext(store, view, params = {}) {
  const wr = coerceWeekRange(params.week_range)
  if (wr) {
    store.commit('setNavScope', { weekRange: wr })
  }

  if (view === 'WeekView') {
    let ids = studentIdsFromParams(params)
    if (!ids.length) {
      ids = [...(store.state.selectedStudentIds || [])]
    }
    if (!ids.length) {
      return {
        ok: false,
        error:
          'WeekView 需在 report-chart 的 params 中指定 student_ids（个体仅 1 人），或在面板先选中学生。',
      }
    }
    store.commit('setSelectedStudents', ids)
    await store.dispatch('fetchSelectedData')
    await store.dispatch('pushNavScopeToServer')
    return { ok: true }
  }

  if (view === 'QuestionView') {
    await store.dispatch('pushNavScopeToServer')
    return { ok: true }
  }

  if (view === 'ScatterView') {
    let ids = studentIdsFromParams(params)
    if (!ids.length) {
      ids = [...(store.state.selectedStudentIds || [])]
    }
    if (!ids.length) {
      const cluster = store.state.studentClusterInfo || {}
      ids = Object.keys(cluster).filter(Boolean)
    }
    if (!ids.length) {
      await store.dispatch('fetchClusterData')
      const cluster = store.state.studentClusterInfo || {}
      ids = Object.keys(cluster).filter(Boolean)
    }
    if (ids.length) {
      store.commit('setSelectedStudents', ids)
      await store.dispatch('fetchSelectedData')
    }
    return { ok: true }
  }

  if (view === 'PortraitView') {
    let ids = studentIdsFromParams(params)
    if (!ids.length) {
      ids = [...(store.state.selectedStudentIds || [])]
    }
    if (!ids.length) {
      return {
        ok: false,
        error:
          'PortraitView 需在 report-chart 的 params 中指定 student_ids（建议该学生 1 人），或在面板先选中学生。',
      }
    }
    store.commit('setSelectedStudents', ids)
    await store.dispatch('fetchSelectedData')
    return { ok: true }
  }

  return {
    ok: false,
    error: `报告内暂不支持嵌入 ${view}，请使用 WeekView / QuestionView / ScatterView / PortraitView，或通过 build_visual_links 跳转 StudentView。`,
  }
}
