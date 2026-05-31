<template>
  <div
    class="agent-skill-step"
    :class="'agent-skill-step--' + (step.status || 'ok')"
  >
    <span class="agent-skill-step-icon">&#128218;</span>
    <span class="agent-skill-step-title">{{ ui.skillStepTitle }}</span>
    <span class="agent-skill-step-name">{{ displayName }}</span>
    <span class="agent-skill-step-status">{{ statusLabel(step.status) }}</span>
  </div>
</template>

<script>
import { AGENT_UI } from '@/constants/agentUiText.js'
import { skillNameFromStep } from '@/utils/agentPlanUtils.js'

export default {
  name: 'AgentSkillStepChip',
  props: {
    step: { type: Object, required: true },
  },
  data() {
    return { ui: AGENT_UI }
  },
  computed: {
    displayName() {
      return skillNameFromStep(this.step) || this.step.summary || ''
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
.agent-skill-step {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid #d0dff5;
  border-radius: 8px;
  background: #f4f8ff;
  font-size: 13px;
  animation: agent-bubble-enter 0.35s ease-out backwards;
}

.agent-skill-step--running {
  border-color: #b8daff;
  background: #f0f7ff;
}

.agent-skill-step--fail,
.agent-skill-step--denied,
.agent-skill-step--blocked {
  border-color: #f5c6cb;
  background: #fffafa;
}

.agent-skill-step-icon { opacity: 0.65; flex-shrink: 0; }

.agent-skill-step-title {
  font-weight: 700;
  color: #377eb8;
  flex-shrink: 0;
}

.agent-skill-step-name {
  flex: 1;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: ui-monospace, monospace;
  font-size: 12px;
}

.agent-skill-step-status {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 10px;
  background: #d4edda;
  color: #155724;
  flex-shrink: 0;
}

.agent-skill-step--fail .agent-skill-step-status,
.agent-skill-step--denied .agent-skill-step-status,
.agent-skill-step--blocked .agent-skill-step-status {
  background: #f8d7da;
  color: #721c24;
}

@keyframes agent-bubble-enter {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
