<template>
  <div class="agent-stream-md">
    <div v-if="!displaySource && active" class="agent-stream-cursor-line">
      <span class="agent-stream-cursor" />
    </div>
    <div v-else class="agent-markdown agent-stream-md-body" v-html="html" @click="onClick" />
    <span
      v-if="active && displaySource && displaySource !== source"
      class="agent-stream-cursor agent-stream-cursor--tail"
    />
  </div>
</template>

<script setup>
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { renderMarkdown } from '@/utils/markdown.js'

const emit = defineEmits(['link-click'])

const props = defineProps({
  source: { type: String, default: '' },
  active: { type: Boolean, default: false },
  /** chars revealed per tick */
  speed: { type: Number, default: 3 },
})

function onClick(e) {
  const anchor = e.target.closest('a')
  if (!anchor) return
  const href = anchor.getAttribute('href')
  if (!href || href === '#') {
    e.preventDefault()
    emit('link-click', anchor.textContent || '')
    return
  }
  if (/View$/.test(href) || href.includes('view=')) {
    e.preventDefault()
    emit('link-click', href)
  }
}

const displaySource = ref('')
let timerId = null
let prevTarget = ''

function clearTimer() {
  if (timerId !== null) {
    clearInterval(timerId)
    timerId = null
  }
}

function syncDisplay() {
  const target = props.source || ''
  if (!props.active) {
    clearTimer()
    displaySource.value = target
    prevTarget = target
    return
  }
  if (target.startsWith(prevTarget) && target.length > prevTarget.length && prevTarget !== '') {
    prevTarget = target
    displaySource.value = target
    return
  }
  prevTarget = target
  if (displaySource.value.length >= target.length) {
    if (displaySource.value.length > target.length) {
      displaySource.value = target
    }
    if (displaySource.value === target) clearTimer()
    return
  }
  if (timerId !== null) return
  timerId = setInterval(() => {
    const tgt = props.source || ''
    if (displaySource.value.length >= tgt.length) {
      clearTimer()
      return
    }
    const remain = tgt.length - displaySource.value.length
    const step = remain > 80 ? props.speed * 3 : remain > 30 ? props.speed * 2 : props.speed
    displaySource.value = tgt.slice(0, displaySource.value.length + step)
  }, 16)
}

watch(() => [props.source, props.active], syncDisplay, { immediate: true })

onBeforeUnmount(clearTimer)

const html = computed(() => renderMarkdown(displaySource.value))
</script>

<style scoped lang="less">
.agent-stream-md-body,
.agent-markdown {
  font-size: 15px;
  line-height: 1.65;
  color: #222;
  word-break: break-word;

  :deep(h1), :deep(h2), :deep(h3), :deep(h4) {
    margin: 14px 0 8px;
    font-weight: 700;
    line-height: 1.35;
  }
  :deep(h1) { font-size: 1.35em; }
  :deep(h2) { font-size: 1.2em; }
  :deep(h3) { font-size: 1.08em; }
  :deep(p) { margin: 8px 0; }
  :deep(ul), :deep(ol) {
    margin: 8px 0;
    padding-left: 22px;
  }
  :deep(li) { margin: 4px 0; }
  :deep(code) {
    background: rgba(0, 0, 0, 0.06);
    padding: 1px 5px;
    border-radius: 4px;
    font-size: 0.92em;
  }
  :deep(pre) {
    background: #1e1e1e;
    color: #eee;
    padding: 12px;
    border-radius: 6px;
    overflow-x: auto;
    margin: 10px 0;
    code { background: none; padding: 0; color: inherit; }
  }
  :deep(table) {
    border-collapse: collapse;
    width: 100%;
    margin: 10px 0;
    font-size: 14px;
  }
  :deep(th), :deep(td) {
    border: 1px solid #ddd;
    padding: 6px 10px;
    text-align: left;
  }
  :deep(th) { background: #f0f0f0; font-weight: 600; }
  :deep(blockquote) {
    margin: 8px 0;
    padding: 6px 12px;
    border-left: 3px solid #ccc;
    color: #555;
  }
  :deep(strong) { font-weight: 700; }
}

.agent-stream-cursor-line {
  min-height: 1.2em;
  padding: 4px 0;
}

.agent-stream-cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  background: #377eb8;
  vertical-align: text-bottom;
  animation: agent-cursor-blink 0.9s step-end infinite;
}

.agent-stream-cursor--tail {
  margin-left: 2px;
}

@keyframes agent-cursor-blink {
  50% { opacity: 0; }
}
</style>

