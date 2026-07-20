<template>
  <div class="agent-scope-attach" :class="{ 'agent-scope-attach--compact': compact }">
    <div class="agent-scope-attach-main">
      <span class="agent-scope-attach-label">{{ title }}</span>
      <span class="agent-scope-attach-meta">{{ meta }}</span>
    </div>
    <div v-if="chips.length" class="agent-scope-attach-ids">
      <span
        v-for="chip in chips"
        :key="chip.key"
        class="agent-scope-attach-id"
        :class="[
          'agent-scope-attach-id--' + chip.kind,
          { 'agent-scope-attach-id--editable': dismissible },
        ]"
      >
        <code>{{ chip.label }}</code>
        <button
          v-if="dismissible"
          type="button"
          class="agent-scope-attach-id-x"
          :title="removeTitle(chip)"
          @click.stop="onRemove(chip)"
        >×</button>
      </span>
    </div>
    <button
      v-if="dismissible"
      type="button"
      class="agent-scope-attach-dismiss"
      :title="ui.scopeAttachDismiss"
      @click="$emit('dismiss')"
    >×</button>
  </div>
</template>

<script>
import { AGENT_UI } from '@/constants/agentUiText.js'
import { formatScopeAttachmentMeta, shortStudentId } from '@/utils/agentScopeAttachment.js'

export default {
  name: 'AgentScopeAttachment',
  props: {
    scope: { type: Object, default: null },
    dismissible: { type: Boolean, default: false },
    compact: { type: Boolean, default: false },
  },
  emits: ['dismiss', 'remove-student', 'remove-class', 'remove-major', 'remove-week'],
  data() {
    return { ui: AGENT_UI }
  },
  computed: {
    title() {
      return this.ui.scopeAttachTitle
    },
    meta() {
      return formatScopeAttachmentMeta(this.scope, this.ui)
    },
    chips() {
      const list = []
      const week = this.scope?.week_range
      if (Array.isArray(week) && week.length >= 2 && week[0] != null && week[1] != null) {
        list.push({
          key: `week-${week[0]}-${week[1]}`,
          kind: 'week',
          label: `第 ${week[0]}–${week[1]} 周`,
        })
      }
      const classes = Array.isArray(this.scope?.classes) ? this.scope.classes.filter(Boolean) : []
      classes.forEach((c) => {
        list.push({ key: `class-${c}`, kind: 'class', label: c, value: c })
      })
      const majors = Array.isArray(this.scope?.majors) ? this.scope.majors.filter(Boolean) : []
      majors.forEach((m) => {
        list.push({ key: `major-${m}`, kind: 'major', label: m, value: m })
      })
      const ids = Array.isArray(this.scope?.selected_student_ids)
        ? this.scope.selected_student_ids.filter(Boolean)
        : []
      ids.forEach((id) => {
        list.push({
          key: `stu-${id}`,
          kind: 'student',
          label: shortStudentId(id),
          value: id,
        })
      })
      return list
    },
  },
  methods: {
    removeTitle(chip) {
      if (chip.kind === 'student') return this.ui.scopeAttachRemoveOne
      if (chip.kind === 'class') return this.ui.scopeAttachRemoveClass
      if (chip.kind === 'major') return this.ui.scopeAttachRemoveMajor
      if (chip.kind === 'week') return this.ui.scopeAttachRemoveWeek
      return this.ui.scopeAttachRemoveOne
    },
    onRemove(chip) {
      if (chip.kind === 'student') this.$emit('remove-student', chip.value)
      else if (chip.kind === 'class') this.$emit('remove-class', chip.value)
      else if (chip.kind === 'major') this.$emit('remove-major', chip.value)
      else if (chip.kind === 'week') this.$emit('remove-week')
    },
  },
}
</script>

<style scoped lang="less">
.agent-scope-attach {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 0 0 8px;
  padding: 8px 28px 8px 10px;
  border: 1px solid #c5dff5;
  border-radius: 8px;
  background: #f0f7ff;
  text-align: left;
}

.agent-scope-attach--compact {
  margin: 0 0 6px;
  padding: 6px 26px 6px 8px;
}

.agent-scope-attach-main {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex-wrap: wrap;
}

.agent-scope-attach-label {
  font-size: 12px;
  font-weight: 600;
  color: #1a5a8a;
  flex-shrink: 0;
}

.agent-scope-attach-meta {
  font-size: 12px;
  color: #456;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-scope-attach-ids {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.agent-scope-attach-id {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 6px;
  background: #e3eef8;
  color: #1a5a8a;
  code {
    font-family: inherit;
    font-size: inherit;
  }
}

.agent-scope-attach-id--week {
  background: #e8f5e9;
  color: #2e7d32;
}

.agent-scope-attach-id--class,
.agent-scope-attach-id--major {
  background: #fff3e0;
  color: #e65100;
}

.agent-scope-attach-id--editable {
  padding-right: 2px;
}

.agent-scope-attach-id-x {
  border: none;
  background: transparent;
  color: inherit;
  opacity: 0.7;
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
  padding: 0 3px;
  border-radius: 3px;
  &:hover {
    opacity: 1;
    background: rgba(0, 0, 0, 0.08);
  }
}

.agent-scope-attach-dismiss {
  position: absolute;
  top: 4px;
  right: 6px;
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: #678;
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
  &:hover {
    background: rgba(0, 0, 0, 0.06);
    color: #333;
  }
}
</style>
