function startOfDay(date) {
  const d = new Date(date)
  d.setHours(0, 0, 0, 0)
  return d.getTime()
}

/**
 * Group sessions by updated_at into 今天 / 昨天 / 7 天内 / 更早
 * @param {Array<{ updated_at?: number }>} sessions
 */
export function groupSessionsByDate(sessions) {
  const now = Date.now()
  const today = startOfDay(now)
  const yesterday = today - 86400000
  const weekAgo = today - 7 * 86400000

  const buckets = {
    today: { label: '今天', items: [] },
    yesterday: { label: '昨天', items: [] },
    week: { label: '7 天内', items: [] },
    older: { label: '更早', items: [] },
  }

  for (const s of sessions || []) {
    const ts = (s.updated_at || 0) * 1000
    const day = startOfDay(ts)
    if (day >= today) buckets.today.items.push(s)
    else if (day >= yesterday) buckets.yesterday.items.push(s)
    else if (day >= weekAgo) buckets.week.items.push(s)
    else buckets.older.items.push(s)
  }

  return [buckets.today, buckets.yesterday, buckets.week, buckets.older].filter(
    (g) => g.items.length > 0,
  )
}

export function filterSessionsByQuery(sessions, query) {
  const q = (query || '').trim().toLowerCase()
  if (!q) return sessions || []
  return (sessions || []).filter((s) => (s.title || '').toLowerCase().includes(q))
}
