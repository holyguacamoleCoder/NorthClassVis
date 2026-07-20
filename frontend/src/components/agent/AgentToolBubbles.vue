<template>
  <TransitionGroup name="agent-bubble-fade" tag="div" class="agent-tool-bubbles">
    <template v-for="(step, i) in steps" :key="stepKey(step, i)">
    <AgentTodoStepCard
      v-if="stepKind(step) === 'todo'"
      :step="step"
      :default-expanded="defaultExpanded"
      :style="{ animationDelay: Math.min(i * 0.05, 0.25) + 's' }"
    />
    <AgentSkillStepChip
      v-else-if="stepKind(step) === 'skill'"
      :step="step"
      :style="{ animationDelay: Math.min(i * 0.05, 0.25) + 's' }"
    />
    <div
      v-else
      class="agent-tool-bubble"
      :class="[
        'agent-tool-bubble--' + (step.status || 'ok'),
        stepKind(step) === 'data' ? 'agent-tool-bubble--data' : '',
      ]"
      :style="{ animationDelay: Math.min(i * 0.05, 0.25) + 's' }"
    >
      <button type="button" class="agent-tool-bubble-header" @click="toggle(i)">
        <span class="agent-tool-bubble-icon">{{ toolIcon(step) }}</span>
        <span v-if="affiliationLabel" class="agent-tool-bubble-affiliation">{{ affiliationLabel }}</span>
        <span class="agent-tool-bubble-name">{{ step.tool }}</span>
        <span v-if="step.resource" class="agent-tool-bubble-resource">{{ step.resource }}</span>
        <span v-if="lineageLabel(step)" class="agent-tool-run-lineage">{{ lineageLabel(step) }}</span>
        <span class="agent-tool-bubble-summary">{{ step.summary }}</span>
        <span v-if="showCancel(step)" class="agent-tool-run-inline">
          <button
            type="button"
            class="agent-tool-run-link agent-tool-run-link--cancel"
            @click.stop="$emit('cancel-run', step.run_id)"
          >{{ ui.runCancel }}</button>
        </span>
        <span v-if="showModify(step)" class="agent-tool-run-inline">
          <button
            type="button"
            class="agent-tool-run-link agent-tool-run-link--modify"
            @click.stop="$emit('derive-run', step)"
          >{{ modifyLabel(step) }}</button>
        </span>
        <span v-if="showAttach(step)" class="agent-tool-run-inline">
          <button
            type="button"
            class="agent-tool-run-link agent-tool-run-link--attach"
            @click.stop="$emit('attach-run', step)"
          >{{ ui.runAttachQuery }}</button>
        </span>
        <span class="agent-tool-bubble-status">{{ statusLabel(step.status) }}</span>
        <span class="agent-tool-bubble-chevron">{{ expanded[i] ? chevronDown : chevronRight }}</span>
      </button>
      <div v-show="expanded[i]" class="agent-tool-bubble-body">
        <div v-if="resultText(step)" class="agent-tool-bubble-row">
          <span class="agent-tool-bubble-label">{{ ui.toolResult }}</span>
          <div class="agent-tool-bubble-result">{{ resultText(step) }}</div>
        </div>
        <div v-if="step.params && Object.keys(step.params).length" class="agent-tool-bubble-row">
          <span class="agent-tool-bubble-label">{{ ui.toolParams }}</span>
          <pre class="agent-tool-bubble-pre">{{ formatParams(step.params) }}</pre>
        </div>
        <div v-if="step.error" class="agent-tool-bubble-row agent-tool-bubble-row--error">
          <span class="agent-tool-bubble-label">{{ ui.toolError }}</span>
          <pre class="agent-tool-bubble-pre agent-tool-bubble-pre--error">{{ step.error }}</pre>
        </div>
        <div v-if="hasRawResult(step)" class="agent-tool-bubble-row agent-tool-bubble-row--raw">
          <button
            type="button"
            class="agent-tool-raw-toggle"
            @click.stop="toggleRaw(i)"
          >{{ rawExpanded[i] ? ui.toolRawResultHide : ui.toolRawResultShow }}</button>
          <pre v-show="rawExpanded[i]" class="agent-tool-bubble-pre agent-tool-bubble-pre--raw">{{ rawPreview(step) }}</pre>
        </div>
      </div>
    </div>
    </template>
  </TransitionGroup>
</template>

<script>
import { AGENT_UI } from '@/constants/agentUiText.js'
import { isModifiableRunStep } from '@/utils/agentTimeline.js'
import {
  formatToolResultPreview,
  toolResultSummaryText,
} from '@/utils/agentPlanUtils.js'
import AgentTodoStepCard from '@/components/agent/AgentTodoStepCard.vue'
import AgentSkillStepChip from '@/components/agent/AgentSkillStepChip.vue'

export default {
  name: 'AgentToolBubbles',
  components: { AgentTodoStepCard, AgentSkillStepChip },
  props: {
    steps: { type: Array, default: () => [] },
    defaultExpanded: { type: Boolean, default: false },
    runActionsEnabled: { type: Boolean, default: true },
    primaryModifyRunId: { type: String, default: '' },
    headerModifyOnly: { type: Boolean, default: false },
    affiliationLabel: { type: String, default: '' },
  },
  emits: ['cancel-run', 'derive-run', 'attach-run'],
  data() {
    return {
      ui: AGENT_UI,
      expanded: {},
      rawExpanded: {},
      chevronDown: '\u25BC',
      chevronRight: '\u25B6',
    }
  },
  watch: {
    steps: {
      immediate: true,
      handler(steps) {
        const next = { ...this.expanded }
        const rawNext = { ...this.rawExpanded }
        ;(steps || []).forEach((step, i) => {
          const failed = ['fail', 'denied', 'blocked'].includes(step?.status)
          if (!(i in next)) {
            next[i] = this.defaultExpanded || failed
          } else if (failed) {
            next[i] = true
          }
          if (!(i in rawNext)) rawNext[i] = false
        })
        Object.keys(next).forEach((k) => {
          if (Number(k) >= (steps || []).length) delete next[k]
        })
        Object.keys(rawNext).forEach((k) => {
          if (Number(k) >= (steps || []).length) delete rawNext[k]
        })
        this.expanded = next
        this.rawExpanded = rawNext
      },
    },
  },
  methods: {
    stepKind(step) {
      if (!step) return 'default'
      if (step.kind === 'todo' || step.tool === 'todo_write') return 'todo'
      if (step.kind === 'skill' || step.tool === 'load_skill') return 'skill'
      if (
        step.kind === 'data' ||
        step.tool === 'query_data' ||
        step.tool === 'aggregate_data' ||
        step.tool === 'inspect_schema'
      ) {
        return 'data'
      }
      return 'default'
    },
    toolIcon(step) {
      const tool = step?.tool || ''
      if (tool === 'query_data') return '\u{1F50D}'
      if (tool === 'aggregate_data') return '\u03A3'
      if (tool === 'inspect_schema') return '\u2637'
      return '\u2699'
    },
    stepKey(step, i) {
      return step.call_id || `${step.tool}-${i}-${step.status || 'ok'}`
    },
    toggle(i) {
      this.expanded[i] = !this.expanded[i]
    },
    toggleRaw(i) {
      this.rawExpanded[i] = !this.rawExpanded[i]
    },
    resultText(step) {
      return toolResultSummaryText(step)
    },
    hasRawResult(step) {
      if (!step || step.status === 'running') return false
      const raw = String(step.raw_content || '').trim()
      if (!raw) return false
      // Failed steps already show error; still allow raw if it adds more than error text
      if (['fail', 'denied', 'blocked'].includes(step.status)) {
        const err = String(step.error || '').trim()
        return raw !== err && raw.length > (err.length || 0)
      }
      return true
    },
    rawPreview(step) {
      return formatToolResultPreview(step?.raw_content || '')
    },
    formatParams(params) {
      try {
        return JSON.stringify(params, null, 2)
      } catch (e) {
        return String(params)
      }
    },
    statusLabel(status) {
      const map = {
        ok: this.ui.toolStatusOk,
        fail: this.ui.toolStatusFail,
        denied: this.ui.toolStatusDenied,
        blocked: this.ui.toolStatusBlocked,
        running: this.ui.runStatusRunning,
        superseded: this.ui.runStatusSuperseded,
        cancelled: this.ui.runStatusCancelled,
      }
      return map[status] || status || this.ui.toolStatusOk
    },
    showCancel(step) {
      if (!this.runActionsEnabled || this.stepKind(step) !== 'data') return false
      return step.status === 'running' && step.run_id
    },
    showModify(step) {
      if (this.headerModifyOnly) return false
      if (!this.runActionsEnabled || this.stepKind(step) !== 'data') return false
      if (!isModifiableRunStep(step)) return false
      const primaryId = this.primaryModifyRunId
      if (primaryId) return step.run_id === primaryId
      return true
    },
    showAttach(step) {
      if (!this.runActionsEnabled || this.stepKind(step) !== 'data') return false
      if (!step?.run_id) return false
      if (['fail', 'denied', 'blocked', 'running', 'pending'].includes(step.status)) return false
      return true
    },
    modifyLabel(step) {
      if (step?.tool === 'aggregate_data') return this.ui.runModifyAggregate
      return this.ui.runModifyQuery
    },
    lineageLabel(step) {
      if (!step?.parent_run_id) return ''
      const patch = step.patch || {}
      const keys = Object.keys(patch)
      const patchHint = keys.length ? ` · ${keys.join(',')}` : ''
      return `${this.ui.runDerivedFrom} #${String(step.parent_run_id).slice(0, 8)}${patchHint}`
    },
  },
}
</script>

<style scoped lang="less">
.agent-tool-bubbles {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.agent-tool-bubble {
  border: 1px solid #dde3ea;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
  text-align: left;
  animation: agent-bubble-enter 0.35s ease-out backwards;
}

.agent-bubble-fade-enter-active {
  transition: opacity 0.35s ease, transform 0.35s ease;
}
.agent-bubble-fade-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

@keyframes agent-bubble-enter {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.agent-tool-bubble--running {
  border-color: #b8daff;
  background: #f0f7ff;
}

.agent-tool-bubble--running .agent-tool-bubble-status {
  background: #cce5ff;
  color: #004085;
}

.agent-tool-bubble--data {
  border-color: #c5dff5;
}

.agent-tool-bubble--data.agent-tool-bubble--fail {
  border-color: #f5c6cb;
}

.agent-tool-bubble-resource {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 8px;
  background: #e8f4fc;
  color: #1a5a8a;
  flex-shrink: 0;
}

.agent-tool-bubble-affiliation {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 8px;
  background: rgba(55, 126, 184, 0.12);
  color: #377eb8;
  flex-shrink: 0;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-tool-bubble--fail .agent-tool-bubble-resource {
  background: #fdecea;
  color: #842029;
}

.agent-tool-bubble-header {
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
  &:hover { background: rgba(0, 0, 0, 0.03); }
}

.agent-tool-bubble-icon {
  opacity: 0.55;
  flex-shrink: 0;
}

.agent-tool-bubble-name {
  font-weight: 700;
  color: #377eb8;
  flex-shrink: 0;
}

.agent-tool-bubble-summary {
  flex: 1;
  min-width: 0;
  color: #555;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-tool-run-inline {
  flex-shrink: 0;
}

.agent-tool-run-link {
  font-size: 11px;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
  &:hover { opacity: 0.85; }
}

.agent-tool-run-link--cancel {
  color: #842029;
}

.agent-tool-run-link--modify {
  color: #0d6efd;
}

.agent-tool-bubble-status {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 10px;
  background: #d4edda;
  color: #155724;
  flex-shrink: 0;
}

.agent-tool-bubble--fail .agent-tool-bubble-status,
.agent-tool-bubble--denied .agent-tool-bubble-status,
.agent-tool-bubble--blocked .agent-tool-bubble-status {
  background: #f8d7da;
  color: #721c24;
}

.agent-tool-bubble-chevron {
  font-size: 10px;
  color: #999;
  flex-shrink: 0;
}

.agent-tool-bubble-body {
  padding: 0 12px 10px;
  border-top: 1px solid #eee;
}

.agent-tool-bubble-row {
  margin-top: 8px;
  font-size: 12px;
}

.agent-tool-bubble--fail,
.agent-tool-bubble--denied,
.agent-tool-bubble--blocked {
  border-color: #f5c6cb;
  background: #fffafa;
}

.agent-tool-bubble-pre--error {
  background: #fff5f5;
  color: #721c24;
  max-height: 180px;
  overflow-y: auto;
}

.agent-tool-bubble-label {
  display: block;
  font-weight: 600;
  color: #666;
  margin-bottom: 4px;
}

.agent-tool-bubble-result {
  padding: 8px 10px;
  background: #f0f6fc;
  border-radius: 4px;
  color: #1a5a8a;
  font-size: 12px;
  line-height: 1.45;
  word-break: break-word;
}

.agent-tool-raw-toggle {
  padding: 0;
  border: none;
  background: transparent;
  color: #377eb8;
  font-size: 12px;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
  &:hover { opacity: 0.85; }
}

.agent-tool-bubble-pre--raw {
  margin-top: 6px;
  max-height: 240px;
  overflow: auto;
  background: #f8fafc;
  color: #334155;
}

.agent-tool-bubble-pre {
  margin: 0;
  padding: 8px;
  background: #f5f5f5;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 11px;
  white-space: pre-wrap;
  word-break: break-all;
}

.agent-tool-run-lineage {
  font-size: 10px;
  color: #6c757d;
  flex-shrink: 0;
}
</style>
