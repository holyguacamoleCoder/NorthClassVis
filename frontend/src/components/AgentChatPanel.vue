<template>
  <div v-if="isShown" class="agent-root agent-root--float">
      <div
        v-if="minimized"
      class="agent-pill"
      @click="$emit('expand')"
    >
      Agent
    </div>

    <div
      v-else
      ref="panel"
      class="agent-panel"
      :style="panelStyle"
    >
      <div
        class="agent-resize-handle"
        @mousedown="startResize"
      ></div>
      <div
        class="agent-panel-header"
        @mousedown="startDrag($event)"
      >
        <div class="agent-header-main">
          <span class="agent-panel-title">{{ sessionTitle }}</span>
          <div class="agent-header-meta">
            <select
              v-model="permissionMode"
              class="agent-mode-select"
              title="能力模式"
              @mousedown.stop
              @click.stop
              @change="onModeChange"
            >
              <option value="consult">咨询</option>
              <option value="analyze">分析</option>
              <option value="produce">产出</option>
            </select>
            <button
              type="button"
              class="agent-header-btn"
              title="会话列表"
              @mousedown.stop
              @click.stop="floatSessionOpen = !floatSessionOpen"
            >
              会话
            </button>
            <button
              type="button"
              class="agent-header-btn"
              :title="ui.memoryRail"
              @mousedown.stop
              @click.stop="openMemoryModal()"
            >
              记忆
            </button>
          </div>
        </div>
        <div class="agent-panel-actions">
          <button
            type="button"
            class="btn-icon btn-icon--text"
            title="全屏页面"
            @mousedown.stop
            @click.stop="goPageMode"
          >全屏</button>
          <button type="button" class="btn-icon" title="新建会话" @mousedown.stop @click.stop="createNewSession">+</button>
          <button type="button" class="btn-icon" title="最小化" @click.stop="$emit('minimize')">−</button>
          <button type="button" class="btn-icon" title="关闭" @click.stop="$emit('close')">×</button>
        </div>
      </div>

      <div
        v-if="floatSessionOpen" class="agent-float-session-overlay" @click.self="floatSessionOpen = false">
        <div class="agent-float-session-drawer" @mousedown.stop>
          <AgentSidebar
            :sessions="sessions"
            :active-id="sessionId"
            :loading="sessionsLoading"
            @create="createNewSession"
            @select="switchSession"
            @rename="renameSessionFromList"
            @delete="deleteSession"
          />
        </div>
      </div>

      <div v-if="todoItems.length" class="agent-plan-bar">
        <span class="agent-plan-label">
          计划<span v-if="planBarMeta" class="agent-plan-meta">（{{ planBarMeta }}）</span>
        </span>
        <span
          v-for="(item, ti) in planBarItems"
          :key="ti"
          class="agent-plan-chip"
          :class="'agent-plan-chip--' + (item.status || 'pending')"
        >{{ todoChipText(item) }}</span>
      </div>

      <div class="agent-panel-body">
        <div class="agent-messages" ref="messagesEl">
          <div
            v-for="(msg, idx) in messages"
            :key="idx"
            :class="['agent-msg', 'agent-msg--' + msg.role]"
          >
            <template v-if="msg.role === 'user'">
              <div class="agent-msg-bubble agent-msg-bubble--user">{{ msg.text }}</div>
            </template>
            <template v-else>
              <AgentAssistantMessage
                :msg="msg"
                :loading="loading"
                :display-steps="displaySteps"
                :reveal-phase="revealPhase"
                :recovery-hint="recoveryHint"
                :summary-status-text="summaryStatusText"
                :visual-link-label="visualLinkLabel"
                :running-tool="msg.streaming ? (msg._runningTool || null) : null"
                @visual-link-click="onVisualLinkClick"
                @report-preview="openReportPreview"
                @report-download="downloadReport"
                @cancel-run="onCancelToolRun"
                @derive-run="onDeriveToolRun"
              />
            </template>
          </div>
          <div v-if="loading && streamingMsgIndex === null" class="agent-msg agent-msg--assistant">
            <div class="agent-msg-bubble agent-msg-bubble--assistant agent-loading">
              <span class="agent-loading-dots">{{ loadingText }}</span><span class="agent-loading-dots-anim">…</span>
            </div>
          </div>
        </div>

        <div v-if="getAgentJumpFeedback" class="agent-jump-feedback">
          {{ getAgentJumpFeedback }}
        </div>
        <div class="agent-input-row">
          <input
            v-model="inputText"
            type="text"
            class="agent-input"
            placeholder="输入问题，如：最近两周链表知识点表现如何？"
            @keydown.enter.prevent="send"
          />
          <button
            v-if="loading"
            type="button"
            class="agent-send agent-send--stop"
            :disabled="!sessionId"
            @click="stopTurn"
          >{{ ui.stop }}</button>
          <button
            v-else
            type="button"
            class="agent-send"
            :disabled="!sessionId"
            @click="send"
          >{{ ui.send }}</button>
        </div>
      </div>

      <AgentMemoriesModal
        :open="memoryModal.open"
        :initial-edit-name="memoryModal.editName"
        :initial-create="memoryModal.create"
        @close="closeMemoryModal"
      />

      <AgentReportPreviewModal
        :open="reportPreview.open"
        :loading="reportPreview.loading"
        :title="reportPreview.title"
        :path="reportPreview.path"
        :content="reportPreview.content"
        :error="reportPreview.error"
        @close="closeReportPreview"
        @download="downloadReport()"
      />

      <div v-if="pendingApproval" class="agent-permission-modal">
        <div class="agent-permission-card" @mousedown.stop>
          <div class="agent-permission-title">需要权限确认</div>
          <p class="agent-permission-reason">{{ pendingApproval.reason }}</p>
          <div class="agent-permission-tool">{{ pendingApproval.tool_name }}</div>
          <pre class="agent-permission-params">{{ formatApprovalParams(pendingApproval.tool_input) }}</pre>
          <div class="agent-permission-actions">
            <button type="button" class="agent-permission-btn agent-permission-btn--deny" @click="resolveApproval('deny')">拒绝</button>
            <button type="button" class="agent-permission-btn" @click="resolveApproval('allow_once')">允许一次</button>
            <button type="button" class="agent-permission-btn agent-permission-btn--primary" @click="resolveApproval('allow_always')">永久允许</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex'
import AgentMarkdown from '@/components/agent/AgentMarkdown.vue'
import AgentStreamingMarkdown from '@/components/agent/AgentStreamingMarkdown.vue'
import AgentToolBubbles from '@/components/agent/AgentToolBubbles.vue'
import AgentAssistantMessage from '@/components/agent/AgentAssistantMessage.vue'
import AgentSidebar from '@/components/agent/AgentSidebar.vue'
import AgentMemoriesModal from '@/components/agent/AgentMemoriesModal.vue'
import AgentReportPreviewModal from '@/components/agent/AgentReportPreviewModal.vue'
import agentChatCore from '@/mixins/agentChatCore.js'
import { modeLabel } from '@/utils/agentAdapter.js'
import { planProgress, planProgressLabel } from '@/utils/agentPlanUtils.js'
import { AGENT_UI } from '@/constants/agentUiText.js'

export default {
  name: 'AgentChatPanel',
  components: {
    AgentMarkdown,
    AgentStreamingMarkdown,
    AgentToolBubbles,
    AgentAssistantMessage,
    AgentSidebar,
    AgentMemoriesModal,
    AgentReportPreviewModal,
  },
  mixins: [agentChatCore],
  props: {
    layout: {
      type: String,
      default: 'float',
      validator: (v) => v === 'float',
    },
    visible: { type: Boolean, default: false },
    minimized: { type: Boolean, default: false },
    context: {
      type: Object,
      default: () => ({}),
    },
  },
  data() {
    return {
      ui: AGENT_UI,
      sessionDrawerOpen: false,
      floatSessionOpen: false,
      memoryModal: { open: false, editName: '', create: false },
      // 拖拽
      useDragPosition: false,
      dragLeft: 0,
      dragTop: 0,
      dragStartX: 0,
      dragStartY: 0,
      panelRect: null,
      // 缩放
      panelWidth: 420,
      panelHeight: 560,
      resizing: false,
      resizeStartX: 0,
      resizeStartY: 0,
      resizeStartW: 0,
      resizeStartH: 0,
      revealTimerId: null,
      streamingMsgIndex: null,
    }
  },
  computed: {
    ...mapGetters(['getAgentJumpFeedback']),
    isShown() {
      return this.visible
    },
    panelStyle() {
      const base = {
        width: this.panelWidth + 'px',
        height: this.panelHeight + 'px',
      }
      if (this.useDragPosition) {
        base.left = this.dragLeft + 'px'
        base.top = this.dragTop + 'px'
        base.right = 'auto'
        base.bottom = 'auto'
      }
      return base
    },
    planBarMeta() {
      return planProgressLabel(this.todoItems)
    },
    planBarItems() {
      const items = [...(this.todoItems || [])]
      const { inProgress } = planProgress(items)
      const active = inProgress ? [inProgress] : []
      const rest = items.filter((i) => i !== inProgress)
      return [...active, ...rest].slice(0, 4)
    },
  },
  watch: {
    visible(val) {
      if (val && !this.sessionId) {
        this.initSession()
      }
    },
  },
  mounted() {
    if (this.visible && !this.sessionId) {
      this.initSession()
    }
  },
  methods: {
    ...mapActions(['openAgentPanel']),
    modeLabel,
    goPageMode() {
      this.$emit('close')
      this.$router.push('/agent')
    },
    openMemoryModal(create = false) {
      this.floatSessionOpen = false
      this.memoryModal = { open: true, editName: '', create: !!create }
    },
    closeMemoryModal() {
      this.memoryModal = { open: false, editName: '', create: false }
    },
    startDrag(e) {
      if (!this.$refs.panel) return
      this.panelRect = this.$refs.panel.getBoundingClientRect()
      this.useDragPosition = true
      this.dragLeft = this.panelRect.left
      this.dragTop = this.panelRect.top
      this.dragStartX = e.clientX
      this.dragStartY = e.clientY
      document.addEventListener('mousemove', this.onDrag)
      document.addEventListener('mouseup', this.stopDrag)
    },
    onDrag(e) {
      this.dragLeft += e.clientX - this.dragStartX
      this.dragTop += e.clientY - this.dragStartY
      this.dragStartX = e.clientX
      this.dragStartY = e.clientY
    },
    stopDrag() {
      document.removeEventListener('mousemove', this.onDrag)
      document.removeEventListener('mouseup', this.stopDrag)
    },
    startResize(e) {
      e.preventDefault()
      e.stopPropagation()
      this.resizing = true
      this.resizeStartX = e.clientX
      this.resizeStartY = e.clientY
      this.resizeStartW = this.panelWidth
      this.resizeStartH = this.panelHeight
      document.addEventListener('mousemove', this.onResize)
      document.addEventListener('mouseup', this.stopResize)
    },
    onResize(e) {
      const dx = e.clientX - this.resizeStartX
      const dy = e.clientY - this.resizeStartY
      let w = this.resizeStartW + dx
      let h = this.resizeStartH + dy
      const minW = 320
      const minH = 400
      const maxW = 900
      const maxH = 900
      w = Math.min(maxW, Math.max(minW, w))
      h = Math.min(maxH, Math.max(minH, h))
      this.panelWidth = w
      this.panelHeight = h
    },
    stopResize() {
      this.resizing = false
      document.removeEventListener('mousemove', this.onResize)
      document.removeEventListener('mouseup', this.stopResize)
    },
    closeFloatSession() {
      this.sessionDrawerOpen = false
      this.floatSessionOpen = false
    },
    async createNewSession() {
      await agentChatCore.methods.createNewSession.call(this)
      this.closeFloatSession()
    },
    async switchSession(sessionId) {
      if (!sessionId || sessionId === this.sessionId) {
        this.closeFloatSession()
        return
      }
      await agentChatCore.methods.switchSession.call(this, sessionId)
      this.closeFloatSession()
    },
    todoChipText(item) {
      const status = item.status || 'pending'
      const prefix = status === 'completed' ? '√' : status === 'in_progress' ? '>' : '·'
      const text = item.content || ''
      return `${prefix} ${text.length > 18 ? text.slice(0, 17) + '…' : text}`
    },
  },
}
</script>

<style scoped lang="less">
.agent-float-root,
.agent-root {
  &--float {
    position: fixed;
    z-index: 1000;
    pointer-events: none;
    & > * {
      pointer-events: auto;
    }
  }
}

.agent-float-session-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.2);
  z-index: 15;
  display: flex;
}

.agent-float-session-drawer {
  width: 260px;
  max-width: 85%;
  height: 100%;
  background: #f7f8fa;
  box-shadow: 4px 0 20px rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow-y: auto;
  padding: 12px;
  box-sizing: border-box;
}

.agent-pill {
  position: fixed;
  right: 24px;
  bottom: 24px;
  padding: 12px 20px;
  background: #2a2a2a;
  color: #fff;
  border-radius: 24px;
  font-weight: 600;
  font-size: 16px;
  cursor: pointer;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.2);
  &:hover {
    background: #333;
  }
}

.agent-panel {
  position: fixed;
  right: 24px;
  bottom: 24px;
  min-width: 320px;
  min-height: 400px;
  max-width: 900px;
  max-height: 900px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  isolation: isolate;
}

.agent-resize-handle {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 20px;
  height: 20px;
  cursor: nwse-resize;
  z-index: 10;
  &::after {
    content: '';
    position: absolute;
    right: 6px;
    bottom: 6px;
    width: 10px;
    height: 10px;
    border-right: 2px solid #999;
    border-bottom: 2px solid #999;
    border-radius: 0 0 4px 0;
  }
  &:hover::after {
    border-color: #333;
  }
}

.agent-panel-header--page {
  cursor: default;
}

.btn-icon--text {
  width: auto;
  padding: 0 10px;
  font-size: 13px;
}

.agent-answer-md {
  margin-top: 4px;
}

.agent-stream-hint {
  font-size: 13px;
  color: #666;
  margin-bottom: 10px;
  padding: 8px 10px;
  background: rgba(0, 0, 0, 0.04);
  border-radius: 6px;
}

.agent-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: #2a2a2a;
  color: #fff;
  cursor: move;
  user-select: none;
}

.agent-panel-title {
  font-weight: 600;
  font-size: 17px;
}

.agent-panel-actions {
  display: flex;
  gap: 6px;
}

.btn-icon {
  width: 32px;
  height: 32px;
  border: none;
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
  border-radius: 4px;
  cursor: pointer;
  font-size: 20px;
  line-height: 1;
  padding: 0;
  &:hover {
    background: rgba(255, 255, 255, 0.3);
  }
}

.agent-panel-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.agent-messages {
  flex: 1;
  overflow-y: auto;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.agent-msg-bubble {
  max-width: 90%;
  padding: 12px 14px;
  border-radius: 10px;
  font-size: 15px;
  line-height: 1.6;
}

.agent-msg-bubble--user {
  align-self: flex-end;
  background: #2a2a2a;
  color: #fff;
}

.agent-msg-bubble--assistant {
  align-self: flex-start;
  background: #f0f0f0;
  color: #333;
}

.agent-msg-bubble--enter {
  animation: agent-fade-in 0.35s ease-out forwards;
}

.agent-answer {
  margin-bottom: 10px;
  font-size: 15px;
}

.agent-status-block {
  margin: 10px 0;
  padding: 8px 10px;
  background: #f8f9fa;
  border-radius: 6px;
  font-size: 14px;
}
.agent-goal-check {
  color: #856404;
  margin-bottom: 4px;
}
.agent-goal-check--satisfied {
  color: #155724;
}
.agent-goal-check-reason {
  color: #666;
  font-size: 12px;
}
.agent-summary-status {
  color: #666;
  margin-bottom: 6px;
}
.agent-key-findings,
.agent-unresolved {
  margin-top: 6px;
  font-size: 13px;
}
.agent-key-findings-label,
.agent-unresolved-label {
  font-weight: 600;
  color: #333;
}
.agent-unresolved ul {
  color: #721c24;
  margin: 2px 0 0;
  padding-left: 18px;
}
.agent-key-findings ul {
  margin: 2px 0 0;
  padding-left: 18px;
}

.agent-section-label {
  font-size: 13px;
  color: #666;
  margin: 10px 0 6px;
  font-weight: 600;
}

.agent-evidence-item {
  display: block;
  font-size: 14px;
  margin: 6px 0;
}

.agent-evidence-tool {
  color: #377eb8;
  margin-right: 8px;
}

.agent-actions ul {
  margin: 0;
  padding-left: 20px;
  font-size: 14px;
  line-height: 1.5;
}

.agent-visual-links {
  margin-top: 10px;
}

.agent-visual-link-btn {
  display: block;
  width: 100%;
  margin-top: 8px;
  padding: 8px 12px;
  text-align: left;
  font-size: 14px;
  border: 1px solid #ccc;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  &:hover {
    background: #f5f5f5;
    border-color: #999;
  }
}

.agent-loading {
  color: #666;
  font-size: 15px;
  animation: agent-pulse 1.4s ease-in-out infinite;
}
.agent-loading-dots-anim {
  display: inline-block;
  animation: agent-dots 1.2s steps(4, end) infinite;
}
@keyframes agent-pulse {
  0%, 100% { opacity: 0.75; }
  50% { opacity: 1; }
}
@keyframes agent-dots {
  0%, 20% { opacity: 0; }
  40%, 100% { opacity: 1; }
}

.agent-reveal {
  animation: agent-fade-in 0.35s ease-out forwards;
}
.agent-stagger {
  animation: agent-fade-in 0.3s ease-out backwards;
}
@keyframes agent-fade-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.trace-fade-enter-active,
.trace-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.trace-fade-enter-from,
.trace-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

.agent-trace {
  border-top: 1px solid #eee;
  padding: 10px 14px;
  background: #fafafa;
}

.agent-trace-toggle {
  width: 100%;
  padding: 8px 0;
  border: none;
  background: none;
  font-size: 14px;
  color: #666;
  cursor: pointer;
  text-align: left;
  &:hover {
    color: #333;
  }
}

.agent-trace-content {
  font-size: 13px;
  color: #666;
  max-height: 220px;
  overflow-y: auto;
  margin-top: 6px;
}

.agent-trace-step {
  border-bottom: 1px solid #eee;
  &:last-child {
    border-bottom: none;
  }
}

.agent-trace-step-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 10px;
  width: 100%;
  padding: 6px 0;
  border: none;
  background: none;
  text-align: left;
  font-size: 13px;
  color: #333;
  cursor: pointer;
  &:hover {
    background: #f0f0f0;
    border-radius: 4px;
  }
}

.agent-trace-tool {
  color: #377eb8;
  font-weight: 600;
}

.agent-trace-summary-inline {
  flex: 1;
  min-width: 0;
  color: #666;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agent-trace-status {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  background: #e9ecef;
  color: #495057;
}
.agent-trace-status--ok {
  background: #d4edda;
  color: #155724;
}
.agent-trace-status--fail {
  background: #f8d7da;
  color: #721c24;
}

.agent-trace-duration {
  font-size: 11px;
  color: #999;
}

.agent-trace-expand-icon {
  font-size: 10px;
  color: #999;
}

.agent-trace-step-detail {
  padding: 8px 0 8px 12px;
  margin-left: 8px;
  border-left: 2px solid #dee2e6;
  font-size: 12px;
  color: #555;
}

.agent-trace-detail-row {
  margin-bottom: 4px;
}
.agent-trace-detail-label {
  font-weight: 600;
  margin-right: 6px;
  color: #333;
}
.agent-trace-detail-error {
  color: #721c24;
}
.agent-trace-params-pre {
  margin: 2px 0 0;
  font-size: 11px;
  word-break: break-all;
  white-space: pre-wrap;
}

.agent-trace-empty {
  color: #999;
  padding: 10px 0;
  font-size: 13px;
}

.agent-jump-feedback {
  padding: 8px 14px;
  font-size: 12px;
  color: #0a7ea4;
  background: #e8f4f8;
  border-top: 1px solid #c5e3ed;
}
.agent-input-row {
  display: flex;
  gap: 10px;
  padding: 12px 14px;
  border-top: 1px solid #eee;
  background: #fff;
}

.agent-input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 15px;
  outline: none;
  &:focus {
    border-color: #2a2a2a;
  }
}

.agent-send {
  padding: 10px 18px;
  background: #2a2a2a;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 15px;
  cursor: pointer;
  &:hover:not(:disabled) {
    background: #333;
  }
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.agent-header-main {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  flex: 1;
}

.agent-header-meta {
  display: flex;
  gap: 8px;
  align-items: center;
}

.agent-mode-select,
.agent-header-btn {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.35);
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  cursor: pointer;
}

.agent-session-drawer {
  max-height: 180px;
  overflow-y: auto;
  border-bottom: 1px solid #eee;
  background: #fafafa;
  padding: 8px 10px;
}

.agent-session-drawer-title {
  font-size: 12px;
  color: #666;
  margin-bottom: 6px;
}

.agent-session-new {
  width: 100%;
  margin-bottom: 8px;
  padding: 6px 8px;
  border: 1px dashed #ccc;
  background: #fff;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}

.agent-session-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  width: 100%;
  padding: 8px;
  margin-bottom: 4px;
  border: 1px solid #eee;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  text-align: left;
}

.agent-session-item--active {
  border-color: #2a2a2a;
  background: #f0f0f0;
}

.agent-session-item-title {
  font-size: 13px;
  font-weight: 600;
}

.agent-session-item-meta {
  font-size: 11px;
  color: #888;
}

.agent-session-empty {
  font-size: 12px;
  color: #999;
  padding: 8px 0;
}

.agent-plan-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  padding: 6px 12px;
  background: #f7f7f7;
  border-bottom: 1px solid #eee;
  font-size: 11px;
}

.agent-plan-label {
  color: #666;
  font-weight: 600;
}

.agent-plan-chip {
  padding: 2px 6px;
  border-radius: 10px;
  background: #eee;
  color: #444;
}

.agent-plan-chip--in_progress {
  background: #fff3cd;
  color: #856404;
}

.agent-plan-chip--completed {
  background: #d4edda;
  color: #155724;
}

.agent-recovery-hint {
  margin-top: 8px;
  padding: 8px 10px;
  background: #fff3cd;
  color: #856404;
  border-radius: 4px;
  font-size: 13px;
}

.agent-permission-modal {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
  padding: 16px;
}

.agent-permission-card {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  width: 100%;
  max-width: 360px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
}

.agent-permission-title {
  font-weight: 700;
  font-size: 15px;
  margin-bottom: 8px;
}

.agent-permission-reason {
  font-size: 13px;
  color: #555;
  margin: 0 0 8px;
}

.agent-permission-tool {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 6px;
}

.agent-permission-params {
  max-height: 120px;
  overflow: auto;
  font-size: 11px;
  background: #f5f5f5;
  padding: 8px;
  border-radius: 4px;
  margin: 0 0 12px;
}

.agent-permission-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.agent-permission-btn {
  padding: 6px 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  font-size: 12px;
}

.agent-permission-btn--primary {
  background: #2a2a2a;
  color: #fff;
  border-color: #2a2a2a;
}

.agent-permission-btn--deny {
  color: #721c24;
  border-color: #f5c6cb;
}
</style>
