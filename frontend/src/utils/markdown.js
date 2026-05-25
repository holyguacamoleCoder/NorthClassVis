import { marked } from 'marked'

marked.setOptions({
  breaks: true,
  gfm: true,
})

export function renderMarkdown(source) {
  const text = String(source || '').trim()
  if (!text) return ''
  return marked.parse(text)
}
