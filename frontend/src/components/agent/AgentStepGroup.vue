<template>
  <div
    class="agent-step-group"
    :class="{
      'agent-step-group--plan': group.phase === 'plan',
      'agent-step-group--update': group.phase === 'plan_update',
      'agent-step-group--process': group.phase === 'process',
    }"
  >
    <div class="agent-step-group-header">
      <button type="button" class="agent-step-group-toggle" @click="expanded = !expanded">
        <span class="agent-step-group-title">{{ title }}</span>
        <span class="agent-step-group-meta">{{ metaLabel }}</span>
        <span class="agent-step-group-chevron">{{ expanded ? chevronDown : chevronRight }}</span>
      </button>
      <button
        v-if="showModifyButton && runActionsEnabled"
        type="button"
        class="agent-tool-run-link agent-tool-run-link--modify"
        @click="$emit('derive-run', primaryModifyStep)"
      >{{ modifyLabel }}</button>
    </div>
    <div v-show="expanded" class="agent-step-group-body">
      <div v-if="group.text" class="agent-step-group-narration">
        <AgentStreamingMarkdown
          v-if="streamNarration"
          :source="group.text"
          :active="true"
          class="agent-thinking-md"
        />
        <AgentMarkdown
          v-else
          :source="group.text"
          class="agent-thinking-md"
        />
      </div>
      <div
        v-for="(item, i) in group.tools"
        :key="toolKey(item, i)"
        class="agent-step-group-tool"
      >
        <AgentToolBubbles
          v-if="item.kind === 'tool' && item.step"
          :steps="[item.step]"
          :default-expanded="isFailed(item.step)"
          :run-actions-enabled="runActionsEnabled"
          :primary-modify-run-id="primaryModifyRunId"
          :affiliation-label="affiliationLabel"
          :header-modify-only="true"
          @cancel-run="$emit('cancel-run', $event)"
          @derive-run="$emit('derive-run', $event)"
          @attach-run="$emit('attach-run', $event)"
        />
      </div>
      <div v-if="runningStep" class="agent-step-group-tool">
        <AgentToolBubbles
          :steps="[runningStep]"
          :default-expanded="true"
          :run-actions-enabled="runActionsEnabled"
          :primary-modify-run-id="primaryModifyRunId"
          :affiliation-label="affiliationLabel"
          :header-modify-only="true"
          @cancel-run="$emit('cancel-run', $event)"
          @derive-run="$emit('derive-run', $event)"
          @attach-run="$emit('attach-run', $event)"
        />
      </div>
    </div>
  </div>
</template>

<script>
import { AGENT_UI } from '@/constants/agentUiText.js'
import { enrichToolStep } from '@/utils/agentPlanUtils.js'
import {
  isModifiableRunStep,
  pickPrimaryModifyRun,
  stepGroupAffiliationLabel,
  stepGroupLabel,
  stepGroupStats,
} from '@/utils/agentTimeline.js'
import AgentMarkdown from '@/components/agent/AgentMarkdown.vue'
import AgentStreamingMarkdown from '@/components/agent/AgentStreamingMarkdown.vue'
import AgentToolBubbles from '@/components/agent/AgentToolBubbles.vue'

export default {
  name: 'AgentStepGroup',
  components: { AgentMarkdown, AgentStreamingMarkdown, AgentToolBubbles },
  props: {
    group: { type: Object, required: true },
    streaming: { type: Boolean, default: false },
    streamNarration: { type: Boolean, default: false },
    runningTool: { type: Object, default: null },
    defaultExpanded: { type: Boolean, default: true },
    runActionsEnabled: { type: Boolean, default: true },
    primaryModifyRunId: { type: String, default: '' },
    showModifyButton: { type: Boolean, default: false },
  },
  emits: ['cancel-run', 'derive-run', 'attach-run'],
  data() {
    return {
      ui: AGENT_UI,
      expanded: this.defaultExpanded,
      chevronDown: '\u25BC',
      chevronRight: '\u25B6',
    }
  },
  computed: {
    title() {
      return stepGroupLabel(this.group, this.ui)
    },
    affiliationLabel() {
      return stepGroupAffiliationLabel(this.group, this.ui)
    },
    metaLabel() {
      const { total, failed } = stepGroupStats(this.group)
      const running = this.runningStep ? 1 : 0
      const n = total + running
      if (!n && !this.group.text) return this.streaming ? '等待中…' : ''
      if (!n) return '无工具调用'
      if (failed) return `${n} 步 · ${failed} 失败`
      if (running) return `${n} 步 · 执行中`
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
      const steps = (this.group.tools || [])
        .filter((item) => item.kind === 'tool' && item.step)
        .map((item) => item.step)
      if (this.runningStep) steps.push(this.runningStep)
      return steps
    },
    primaryModifyStep() {
      return pickPrimaryModifyRun(this.allToolSteps)
    },
    modifyLabel() {
      const step = this.primaryModifyStep
      if (!step) return this.ui.runModifyProcess
      if (step.tool === 'aggregate_data') return this.ui.runModifyAggregate
      return this.ui.runModifyQuery
    },
  },
  watch: {
    defaultExpanded: {
      immediate: true,
      handler(val) {
        this.expanded = val
      },
    },
    runningTool(val) {
      if (val) this.expanded = true
    },
    group: {
      deep: true,
      handler() {
        const { failed } = stepGroupStats(this.group)
        if (failed > 0) this.expanded = true
      },
    },
  },
  methods: {
    toolKey(item, i) {
      if (item.kind === 'tool' && item.step?.call_id) {
        return `tool-${item.step.call_id}`
      }
      return `tool-${i}`
    },
    isFailed(step) {
      return ['fail', 'denied', 'blocked'].includes(step?.status)
    },
  },
}
</script>

<style scoped lang="less">
.agent-step-group {
  margin-bottom: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: rgba(55, 126, 184, 0.04);
  overflow: hidden;
}

.agent-step-group--plan {
  border-left: 3px solid #377eb8;
}

.agent-step-group--update {
  background: rgba(55, 126, 184, 0.03);
  border-left: 3px solid #5a9fd4;
}

.agent-step-group--process {
  border-left: 3px solid #94a3b8;
  background: #fafbfc;
}

.agent-step-group-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 10px 0 0;
}

.agent-step-group-toggle {
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

.agent-step-group-title {
  font-size: 13px;
  font-weight: 600;
  color: #444;
}

.agent-step-group-meta {
  flex: 1;
  font-size: 12px;
  color: #888;
  text-align: right;
}

.agent-step-group-chevron {
  font-size: 10px;
  color: #999;
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
  color: #0d6efd;
  flex-shrink: 0;
  &:hover { opacity: 0.85; }
}

.agent-step-group-body {
  padding: 0 10px 10px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.agent-step-group-narration {
  margin-top: 8px;
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 4px;
}

.agent-thinking-md {
  font-size: 14px;
  color: #444;
}

.agent-step-group-tool {
  margin-top: 8px;
}

.agent-step-group-tool :deep(.agent-tool-bubbles) {
  margin-bottom: 0;
}
</style>
