<template>
  <div
    class="agent-subagent-step"
    :class="[
      'agent-subagent-step--' + (step.status || 'ok'),
      expanded ? 'agent-subagent-step--expanded' : '',
    ]"
  >
    <button type="button" class="agent-subagent-step-header" @click="expanded = !expanded">
      <span class="agent-subagent-step-icon">&#129302;</span>
      <span class="agent-subagent-step-title">{{ ui.subagentStepTitle }}</span>
      <span class="agent-subagent-step-kind">{{ kindLabel }}</span>
      <span v-if="turnsLabel" class="agent-subagent-step-turns">{{ turnsLabel }}</span>
      <span class="agent-subagent-step-summary">{{ headerSummary }}</span>
      <span class="agent-subagent-step-status">{{ statusLabel(step.status) }}</span>
      <span class="agent-subagent-step-chevron">{{ expanded ? chevronDown : chevronRight }}</span>
    </button>

    <div v-show="expanded" class="agent-subagent-step-body">
      <div v-if="taskPreview" class="agent-subagent-step-row">
        <span class="agent-subagent-step-label">{{ ui.subagentTask }}</span>
        <p class="agent-subagent-step-task">{{ taskPreview }}</p>
      </div>

      <div v-if="innerSteps.length" class="agent-subagent-step-inner">
        <div class="agent-subagent-step-label">{{ ui.subagentInnerTools }}</div>
        <ul class="agent-subagent-inner-list">
          <li
            v-for="(inner, i) in innerSteps"
            :key="inner.call_id || `${inner.tool}-${i}`"
            class="agent-subagent-inner-item"
            :class="'agent-subagent-inner-item--' + (inner.status || 'ok')"
          >
            <span class="agent-subagent-inner-tool">{{ inner.tool }}</span>
            <span v-if="inner.resource" class="agent-subagent-inner-resource">{{ inner.resource }}</span>
            <span class="agent-subagent-inner-summary">{{ innerToolSummary(inner) }}</span>
            <span class="agent-subagent-inner-status">{{ statusLabel(inner.status) }}</span>
          </li>
        </ul>
      </div>

      <div v-if="refs.length" class="agent-subagent-step-row">
        <span class="agent-subagent-step-label">{{ ui.subagentRefs }}</span>
        <ul class="agent-subagent-refs">
          <li v-for="(ref, i) in refs" :key="i">{{ ref }}</li>
        </ul>
      </div>

      <div v-if="resultSummary" class="agent-subagent-step-row">
        <span class="agent-subagent-step-label">{{ ui.subagentSummary }}</span>
        <pre class="agent-subagent-step-pre">{{ resultSummary }}</pre>
      </div>

      <div v-if="step.error || parsed.error" class="agent-subagent-step-row agent-subagent-step-row--error">
        <span class="agent-subagent-step-label">{{ ui.toolError }}</span>
        <pre class="agent-subagent-step-pre agent-subagent-step-pre--error">{{ step.error || parsed.error }}</pre>
      </div>
    </div>
  </div>
</template>

<script>
import { AGENT_UI } from '@/constants/agentUiText.js'
import {
  innerToolSummary,
  parseSubagentToolResult,
  subagentKindLabel,
  summarizeSubagentStep,
} from '@/utils/agentSubagent.js'

export default {
  name: 'AgentSubagentStepCard',
  props: {
    step: { type: Object, required: true },
    defaultExpanded: { type: Boolean, default: false },
  },
  data() {
    return {
      ui: AGENT_UI,
      expanded: this.defaultExpanded,
      chevronDown: '\u25BC',
      chevronRight: '\u25B6',
      innerToolSummary,
    }
  },
  computed: {
    subagent() {
      return this.step?.subagent || {}
    },
    parsed() {
      return parseSubagentToolResult(this.step?.raw_content || '')
    },
    kindLabel() {
      const kind = this.subagent.kind || this.step?.params?.kind || this.parsed.kind
      return subagentKindLabel(kind)
    },
    taskPreview() {
      return (
        this.subagent.task_preview
        || this.step?.params?.task
        || ''
      ).trim()
    },
    innerSteps() {
      const list = this.subagent.inner_steps
      return Array.isArray(list) ? list : []
    },
    refs() {
      const fromSub = this.subagent.refs
      if (Array.isArray(fromSub) && fromSub.length) return fromSub
      return this.parsed.refs || []
    },
    turnsLabel() {
      const turns = this.subagent.turns || this.parsed.turns
      if (!turns) return ''
      return this.ui.subagentTurns(turns)
    },
    resultSummary() {
      return (this.subagent.summary || this.parsed.summary || '').trim()
    },
    headerSummary() {
      if (this.step.status === 'running') {
        const running = this.innerSteps.filter((s) => s.status === 'running').pop()
        if (running?.tool) return `${running.tool}…`
      }
      return summarizeSubagentStep(this.step)
    },
  },
  watch: {
    step: {
      immediate: true,
      handler(step) {
        const failed = ['fail', 'denied', 'blocked'].includes(step?.status)
        if (this.defaultExpanded || failed) this.expanded = true
      },
    },
  },
  methods: {
    statusLabel(status) {
      const map = {
        ok: this.ui.toolStatusOk,
        fail: this.ui.toolStatusFail,
        denied: this.ui.toolStatusDenied,
        blocked: this.ui.toolStatusBlocked,
        running: this.ui.toolStatusRunning,
      }
      return map[status] || status || this.ui.toolStatusOk
    },
  },
}
</script>

<style scoped lang="less">
.agent-subagent-step {
  border: 1px solid #c9b8f0;
  border-radius: 10px;
  background: linear-gradient(135deg, #faf8ff 0%, #f3f0ff 100%);
  overflow: hidden;
  animation: agent-bubble-enter 0.35s ease-out backwards;
}

.agent-subagent-step--running {
  border-color: #a78bfa;
  background: linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%);
}

.agent-subagent-step--fail,
.agent-subagent-step--denied,
.agent-subagent-step--blocked {
  border-color: #f5c6cb;
  background: #fffafa;
}

.agent-subagent-step-header {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 12px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  text-align: left;
  &:hover { background: rgba(124, 58, 237, 0.06); }
}

.agent-subagent-step-icon { flex-shrink: 0; opacity: 0.85; }

.agent-subagent-step-title {
  font-weight: 700;
  color: #6d28d9;
  flex-shrink: 0;
}

.agent-subagent-step-kind {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
  background: #ede9fe;
  color: #5b21b6;
  flex-shrink: 0;
}

.agent-subagent-step-turns {
  font-size: 11px;
  color: #7c3aed;
  flex-shrink: 0;
}

.agent-subagent-step-summary {
  flex: 1;
  min-width: 0;
  color: #555;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-subagent-step-status {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 10px;
  background: #ddd6fe;
  color: #4c1d95;
  flex-shrink: 0;
}

.agent-subagent-step--fail .agent-subagent-step-status {
  background: #f8d7da;
  color: #721c24;
}

.agent-subagent-step-chevron {
  font-size: 10px;
  color: #999;
  flex-shrink: 0;
}

.agent-subagent-step-body {
  padding: 0 12px 12px;
  border-top: 1px solid #e9e5f5;
}

.agent-subagent-step-row {
  margin-top: 10px;
  font-size: 12px;
}

.agent-subagent-step-row--error .agent-subagent-step-pre {
  background: #fff5f5;
  color: #721c24;
}

.agent-subagent-step-label {
  display: block;
  font-weight: 600;
  color: #666;
  margin-bottom: 4px;
}

.agent-subagent-step-task {
  margin: 0;
  color: #444;
  line-height: 1.5;
  white-space: pre-wrap;
}

.agent-subagent-inner-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.agent-subagent-inner-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  background: #fff;
  border: 1px solid #e9e5f5;
  font-size: 12px;
}

.agent-subagent-inner-item--running {
  border-color: #c4b5fd;
  background: #faf5ff;
}

.agent-subagent-inner-tool {
  font-weight: 600;
  color: #6d28d9;
  flex-shrink: 0;
}

.agent-subagent-inner-resource {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 8px;
  background: #e8f4fc;
  color: #1a5a8a;
  flex-shrink: 0;
}

.agent-subagent-inner-summary {
  flex: 1;
  min-width: 0;
  color: #555;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-subagent-inner-status {
  font-size: 10px;
  color: #888;
  flex-shrink: 0;
}

.agent-subagent-refs {
  margin: 0;
  padding-left: 18px;
  color: #444;
  font-size: 11px;
  font-family: ui-monospace, monospace;
}

.agent-subagent-step-pre {
  margin: 0;
  padding: 8px;
  background: #f5f5f5;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 11px;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 200px;
  overflow-y: auto;
}

@keyframes agent-bubble-enter {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
