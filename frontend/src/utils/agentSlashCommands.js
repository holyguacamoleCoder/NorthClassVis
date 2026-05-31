/** Client-side slash command helpers (execution is on the backend). */

export function parseSkillSlashCommand(text) {
  const stripped = String(text || '').trim()
  if (!stripped.startsWith('/')) return null
  const parts = stripped.split(/\s+/)
  const head = parts[0].toLowerCase()
  if (head !== '/skill' && head !== '/skills') return null
  return {
    kind: 'skill',
    args: parts.slice(1),
    skillName: parts.length > 1 && !['list', 'ls', 'help', '?', 'h'].includes(parts[1].toLowerCase())
      ? parts[1]
      : null,
  }
}

export function isSkillSlashCommand(text) {
  return parseSkillSlashCommand(text) !== null
}

export function skillCommandLoadingText(text) {
  const cmd = parseSkillSlashCommand(text)
  if (!cmd) return '思考中'
  if (!cmd.skillName) return '列出技能'
  return `加载技能 ${cmd.skillName}`
}
