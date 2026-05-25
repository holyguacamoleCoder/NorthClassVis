<template>
  <TransitionGroup name="agent-bubble-fade" tag="div" class="agent-tool-bubbles">
    <div
      v-for="(step, i) in steps"
      :key="stepKey(step, i)"
      class="agent-tool-bubble"
      :class="'agent-tool-bubble--' + (step.status || 'ok')"
      :style="{ animationDelay: Math.min(i * 0.05, 0.25) + 's' }"
    >
      <button type="button" class="agent-tool-bubble-header" @click="toggle(i)">
        <span class="agent-tool-bubble-icon">&#9881;</span>
        <span class="agent-tool-bubble-name">{{ step.tool }}</span>
        <span class="agent-tool-bubble-summary">{{ step.summary }}</span>
        <span class="agent-tool-bubble-status">{{ statusLabel(step.status) }}</span>
        <span class="agent-tool-bubble-chevron">{{ expanded[i] ? chevronDown : chevronRight }}</span>
      </button>
      <div v-show="expanded[i]" class="agent-tool-bubble-body">
        <div v-if="step.params && Object.keys(step.params).length" class="agent-tool-bubble-row">
          <span class="agent-tool-bubble-label">{{ ui.toolParams }}</span>
          <pre class="agent-tool-bubble-pre">{{ formatParams(step.params) }}</pre>
        </div>
        <div v-if="step.error" class="agent-tool-bubble-row agent-tool-bubble-row--error">
          <span class="agent-tool-bubble-label">{{ ui.toolError }}</span>
          <span>{{ step.error }}</span>
        </div>
      </div>
    </div>
  </TransitionGroup>
</template>

<script>
import { AGENT_UI } from '@/constants/agentUiText.js'

export default {
  name: 'AgentToolBubbles',
  props: {
    steps: { type: Array, default: () => [] },
    defaultExpanded: { type: Boolean, default: false },
  },
  data() {
    return {
      ui: AGENT_UI,
      expanded: {},
      chevronDown: '\u25BC',
      chevronRight: '\u25B6',
    }
  },
  watch: {
    steps: {
      immediate: true,
      handler(steps) {
        const next = { ...this.expanded }
        ;(steps || []).forEach((_, i) => {
          if (!(i in next)) {
            next[i] = this.defaultExpanded
          }
        })
        Object.keys(next).forEach((k) => {
          if (Number(k) >= (steps || []).length) delete next[k]
        })
        this.expanded = next
      },
    },
  },
  methods: {
    stepKey(step, i) {
      return step.call_id || `${step.tool}-${i}-${step.status || 'ok'}`
    },
    toggle(i) {
      this.expanded[i] = !this.expanded[i]
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
        running: this.ui.toolStatusRunning,
      }
      return map[status] || status || this.ui.toolStatusOk
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

.agent-tool-bubble--fail,
.agent-tool-bubble--denied,
.agent-tool-bubble--blocked {
  border-color: #f5c6cb;
  background: #fffafa;
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
  color: #555;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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

.agent-tool-bubble-row--error { color: #721c24; }

.agent-tool-bubble-label {
  display: block;
  font-weight: 600;
  color: #666;
  margin-bottom: 4px;
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
</style>
