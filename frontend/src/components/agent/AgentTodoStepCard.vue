<template>
  <div
    class="agent-todo-step"
    :class="'agent-todo-step--' + (step.status || 'ok')"
  >
    <button type="button" class="agent-todo-step-header" @click="expanded = !expanded">
      <span class="agent-todo-step-icon">&#9745;</span>
      <span class="agent-todo-step-title">{{ ui.todoStepTitle }}</span>
      <span class="agent-todo-step-summary">{{ headerSummary }}</span>
      <span class="agent-todo-step-status">{{ statusLabel(step.status) }}</span>
      <span class="agent-todo-step-chevron">{{ expanded ? chevronDown : chevronRight }}</span>
    </button>
    <ul v-show="expanded" class="agent-todo-step-list">
      <li
        v-for="(item, i) in items"
        :key="i"
        class="agent-todo-step-item"
        :class="'agent-todo-step-item--' + (item.status || 'pending')"
      >
        <span class="agent-todo-step-item-icon">{{ todoIcon(item.status) }}</span>
        <div class="agent-todo-step-item-body">
          <span class="agent-todo-step-item-text">{{ item.content }}</span>
          <span v-if="item.status === 'in_progress' && item.active_form" class="agent-todo-step-active">
            {{ item.active_form }}
          </span>
          <span v-if="item.acceptance" class="agent-todo-step-acceptance">
            {{ ui.todoAcceptance }}：{{ item.acceptance }}
          </span>
        </div>
      </li>
    </ul>
  </div>
</template>

<script>
import { AGENT_UI } from '@/constants/agentUiText.js'
import { planProgress, todoIcon, todoItemsFromStep } from '@/utils/agentPlanUtils.js'

export default {
  name: 'AgentTodoStepCard',
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
      todoIcon,
    }
  },
  computed: {
    items() {
      return todoItemsFromStep(this.step)
    },
    headerSummary() {
      const { completed, total } = planProgress(this.items)
      if (!total) return this.step.summary || ''
      return `${completed}/${total} ${this.ui.todoStepDone}`
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
.agent-todo-step {
  border: 1px solid #d4e8d4;
  border-radius: 8px;
  background: #f8fcf8;
  overflow: hidden;
  animation: agent-bubble-enter 0.35s ease-out backwards;
}

.agent-todo-step--running {
  border-color: #b8daff;
  background: #f0f7ff;
}

.agent-todo-step--fail,
.agent-todo-step--denied,
.agent-todo-step--blocked {
  border-color: #f5c6cb;
  background: #fffafa;
}

.agent-todo-step-header {
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

.agent-todo-step-icon { opacity: 0.6; flex-shrink: 0; }
.agent-todo-step-title { font-weight: 700; color: #2d6a2d; flex-shrink: 0; }
.agent-todo-step-summary { flex: 1; color: #555; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.agent-todo-step-status {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 10px;
  background: #d4edda;
  color: #155724;
  flex-shrink: 0;
}

.agent-todo-step-chevron { font-size: 10px; color: #999; flex-shrink: 0; }

.agent-todo-step-list {
  list-style: none;
  margin: 0;
  padding: 0 12px 10px;
  border-top: 1px solid #e8f0e8;
}

.agent-todo-step-item {
  display: flex;
  gap: 8px;
  padding: 6px 0;
  font-size: 12px;
  border-bottom: 1px solid #f0f4f0;
  &:last-child { border-bottom: none; }
}

.agent-todo-step-item-icon {
  flex-shrink: 0;
  width: 16px;
  text-align: center;
  color: #666;
}

.agent-todo-step-item--completed .agent-todo-step-item-text {
  color: #888;
  text-decoration: line-through;
}

.agent-todo-step-item--in_progress .agent-todo-step-item-text {
  font-weight: 600;
  color: #856404;
}

.agent-todo-step-item-body {
  flex: 1;
  min-width: 0;
}

.agent-todo-step-item-text { line-height: 1.4; color: #333; }

.agent-todo-step-active {
  display: block;
  margin-top: 2px;
  font-size: 11px;
  color: #856404;
}

.agent-todo-step-acceptance {
  display: block;
  margin-top: 2px;
  font-size: 11px;
  color: #777;
}

@keyframes agent-bubble-enter {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
