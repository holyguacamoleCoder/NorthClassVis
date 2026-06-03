<template>
  <div class="agent-process-timeline">
    <div class="agent-process-header">
      <button type="button" class="agent-process-toggle" @click="expanded = !expanded">
        <span class="agent-section-label">{{ ui.sectionProcess }}</span>
        <span class="agent-process-meta">{{ metaLabel }}</span>
        <span class="agent-process-chevron">{{ expanded ? chevronDown : chevronRight }}</span>
      </button>
      <button
        v-if="primaryModifyStep && runActionsEnabled"
        type="button"
        class="agent-tool-run-link agent-tool-run-link--modify"
        @click="$emit('derive-run', primaryModifyStep)"
      >{{ processModifyLabel }}</button>
    </div>
    <div v-show="expanded" class="agent-process-body">
      <div
        v-for="(item, i) in items"
        :key="itemKey(item, i)"
        class="agent-process-item"
        :class="'agent-process-item--' + item.kind"
      >
        <div v-if="item.kind === 'narration'" class="agent-process-narration">
          <AgentMarkdown :source="item.text || ''" class="agent-process-narration-md" />
        </div>
        <AgentToolBubbles
          v-else-if="item.kind === 'tool' && item.step"
          :steps="[item.step]"
          :default-expanded="isFailed(item.step)"
          :run-actions-enabled="runActionsEnabled"
          :primary-modify-run-id="primaryModifyRunId"
          :header-modify-only="true"
          @cancel-run="$emit('cancel-run', $event)"
          @derive-run="$emit('derive-run', $event)"
        />
      </div>
      <div v-if="runningStep" class="agent-process-item agent-process-item--tool">
        <AgentToolBubbles
          :steps="[runningStep]"
          :default-expanded="true"
          :run-actions-enabled="runActionsEnabled"
          :primary-modify-run-id="primaryModifyRunId"
          :header-modify-only="true"
          @cancel-run="$emit('cancel-run', $event)"
          @derive-run="$emit('derive-run', $event)"
        />
      </div>
    </div>
  </div>
</template>

<script>
import { AGENT_UI } from '@/constants/agentUiText.js'
import { enrichToolStep } from '@/utils/agentPlanUtils.js'
import { pickPrimaryModifyRun, processTimelineStats } from '@/utils/agentTimeline.js'
import AgentMarkdown from '@/components/agent/AgentMarkdown.vue'
import AgentToolBubbles from '@/components/agent/AgentToolBubbles.vue'

export default {
  name: 'AgentProcessTimeline',
  components: { AgentMarkdown, AgentToolBubbles },
  props: {
    items: { type: Array, default: () => [] },
    runningTool: { type: Object, default: null },
    streaming: { type: Boolean, default: false },
    defaultExpanded: { type: Boolean, default: false },
    runActionsEnabled: { type: Boolean, default: true },
  },
  emits: ['cancel-run', 'derive-run'],
  data() {
    return {
      ui: AGENT_UI,
      expanded: this.defaultExpanded,
      chevronDown: '\u25BC',
      chevronRight: '\u25B6',
    }
  },
  computed: {
    metaLabel() {
      const { total, failed } = processTimelineStats(this.items)
      const running = this.runningStep ? 1 : 0
      const n = total + running
      if (!n) return this.streaming ? '执行中…' : '无步骤'
      if (failed) return `${n} 步 · ${failed} 失败`
      return `${n} 步`
    },
    runningStep() {
      const rt = this.runningTool
      if (!rt || !rt.tool) return null
      const tool = rt.tool
      return enrichToolStep({
        call_id: rt.call_id,
        run_id: rt.run_id,
        parent_run_id: rt.parent_run_id,
        patch: rt.patch,
        derive_strategy: rt.derive_strategy,
        tool,
        params: rt.params || {},
        summary: tool === 'todo_write' ? '更新计划中…' : tool === 'load_skill' ? '加载技能中…' : '执行中…',
        status: 'running',
        run_status: 'executing',
      })
    },
    allToolSteps() {
      const steps = (this.items || [])
        .filter((item) => item.kind === 'tool' && item.step)
        .map((item) => item.step)
      if (this.runningStep) steps.push(this.runningStep)
      return steps
    },
    primaryModifyStep() {
      return pickPrimaryModifyRun(this.allToolSteps)
    },
    primaryModifyRunId() {
      return this.primaryModifyStep?.run_id || ''
    },
    processModifyLabel() {
      const step = this.primaryModifyStep
      if (!step) return this.ui.runModifyProcess
      if (step.tool === 'aggregate_data') return this.ui.runModifyAggregate
      return this.ui.runModifyQuery
    },
  },
  watch: {
    items: {
      immediate: true,
      handler(items) {
        const { failed } = processTimelineStats(items)
        if (failed > 0 || this.defaultExpanded) {
          this.expanded = true
        }
      },
    },
    runningTool(val) {
      if (val) this.expanded = true
    },
  },
  methods: {
    itemKey(item, i) {
      if (item.kind === 'tool' && item.step?.call_id) {
        return `tool-${item.step.call_id}`
      }
      return `n-${i}-${(item.text || '').slice(0, 24)}`
    },
    isFailed(step) {
      return ['fail', 'denied', 'blocked'].includes(step?.status)
    },
  },
}
</script>

<style scoped lang="less">
.agent-process-timeline {
  margin: 10px 0;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fafbfc;
  overflow: hidden;
}

.agent-process-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 12px 0 0;
}

.agent-process-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
  padding: 8px 0 8px 12px;
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
  &:hover { background: rgba(0, 0, 0, 0.03); }
}

.agent-tool-run-link {
  font-size: 11px;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
  color: #0d6efd;
  flex-shrink: 0;
  &:hover { opacity: 0.85; }
}

.agent-process-meta {
  flex: 1;
  font-size: 12px;
  color: #888;
  text-align: right;
}

.agent-process-chevron {
  font-size: 10px;
  color: #999;
  flex-shrink: 0;
}

.agent-process-body {
  padding: 0 10px 10px;
  border-top: 1px solid #eee;
}

.agent-process-item {
  margin-top: 8px;
}

.agent-process-narration {
  padding: 6px 10px;
  background: #fff;
  border-left: 2px solid #94a3b8;
  border-radius: 4px;
  font-size: 13px;
  color: #555;
}

.agent-process-narration-md {
  font-size: 13px;
}

.agent-process-item--tool :deep(.agent-tool-bubbles) {
  margin-bottom: 0;
}
</style>
