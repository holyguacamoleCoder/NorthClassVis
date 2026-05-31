<template>
  <AgentPageShell
    :session-title="sessionTitle"
    :sidebar-open="pageSidebarOpen"
    :rail-open="pageRailOpen"
    @back="goDashboard"
    @float="goFloatMode"
    @toggle-sidebar="pageSidebarOpen = !pageSidebarOpen"
    @toggle-rail="pageRailOpen = !pageRailOpen"
    @title-save="renameSession"
  >
    <template #sidebar>
      <AgentSidebar
        :sessions="sessions"
        :active-id="sessionId"
        :loading="sessionsLoading"
        @create="createNewSession"
        @select="switchSession"
        @rename="renameSessionFromList"
        @delete="deleteSession"
      />
    </template>

    <div class="agent-page-chat">
      <div class="agent-panel-body agent-panel-body--page">
        <div
          class="agent-messages agent-messages--page"
          :class="{ 'agent-messages--empty': !messages.length && !loading }"
          ref="messagesEl"
          @scroll="onMessagesScroll"
        >
          <div v-if="!messages.length && !loading" class="agent-empty-state">
            <h2 class="agent-empty-title">{{ ui.emptyTitle }}</h2>
            <p class="agent-empty-desc">{{ ui.emptyDesc }}</p>
            <div class="agent-empty-chips">
              <button
                v-for="(q, qi) in sampleQuestions"
                :key="qi"
                type="button"
                class="agent-empty-chip"
                @click="fillSampleQuestion(q)"
              >{{ q }}</button>
            </div>
            <div v-if="catalogSkills.length" class="agent-empty-chips agent-empty-chips--skills">
              <button
                type="button"
                class="agent-empty-chip agent-empty-chip--cmd"
                @click="fillSkillCommand()"
              >{{ ui.emptySkillList }}</button>
              <button
                v-for="s in catalogSkills"
                :key="s.name"
                type="button"
                class="agent-empty-chip agent-empty-chip--cmd"
                :title="s.description"
                @click="fillSkillCommand(s.name)"
              >/skill {{ s.name }}</button>
            </div>
          </div>

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
                :display-steps="displaySteps"
                :reveal-phase="revealPhase"
                :recovery-hint="recoveryHint"
                :summary-status-text="summaryStatusText"
                :visual-link-label="visualLinkLabel"
                :running-tool="msg.streaming ? (msg._runningTool || null) : null"
                @visual-link-click="onVisualLinkClick"
                @report-preview="openReportPreview"
                @report-download="downloadReport"
              />
            </template>
          </div>

          <div v-if="loading && streamingMsgIndex === null" class="agent-msg agent-msg--assistant">
            <div class="agent-msg-bubble agent-msg-bubble--assistant agent-loading">
              <span>{{ loadingText }}</span><span class="agent-loading-dots-anim">?</span>
            </div>
          </div>
        </div>

        <div class="agent-composer-wrap">
          <div class="agent-composer-inner">
            <textarea
              ref="composerEl"
              v-model="inputText"
              class="agent-composer"
              :placeholder="ui.composerPlaceholder"
              rows="1"
              @keydown="onComposerKeydown"
              @input="autoResizeComposer"
            />
            <button
              v-if="loading"
              type="button"
              class="agent-send agent-send--page agent-send--stop"
              :disabled="!sessionId"
              @click="stopTurn"
            >{{ ui.stop }}</button>
            <button
              v-else
              type="button"
              class="agent-send agent-send--page"
              :disabled="!sessionId"
              @click="send"
            >{{ ui.send }}</button>
          </div>
          <div class="agent-composer-hint">{{ ui.composerHint }}</div>
        </div>
      </div>
    </div>

    <template #rail>
      <AgentContextRail
        :permission-mode="permissionMode"
        :todo-items="todoItems"
        :loaded-skills="loadedSkills"
        :message-count="messageCount"
        @update:permission-mode="onRailModeChange"
        @open-dashboard="goDashboard"
      />
    </template>

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

    <div v-if="pendingApproval" class="agent-permission-modal agent-permission-modal--page">
      <div class="agent-permission-card" @mousedown.stop>
        <div class="agent-permission-title">{{ ui.permissionTitle }}</div>
        <p class="agent-permission-reason">{{ pendingApproval.reason }}</p>
        <div class="agent-permission-tool">{{ pendingApproval.tool_name }}</div>
        <pre class="agent-permission-params">{{ formatApprovalParams(pendingApproval.tool_input) }}</pre>
        <div class="agent-permission-actions">
          <button type="button" class="agent-permission-btn agent-permission-btn--deny" @click="resolveApproval('deny')">{{ ui.deny }}</button>
          <button type="button" class="agent-permission-btn" @click="resolveApproval('allow_once')">{{ ui.allowOnce }}</button>
          <button type="button" class="agent-permission-btn agent-permission-btn--primary" @click="resolveApproval('allow_always')">{{ ui.allowAlways }}</button>
        </div>
      </div>
    </div>
  </AgentPageShell>
</template>

<script>
import { mapActions } from 'vuex'
import agentChatCore from '@/mixins/agentChatCore.js'
import AgentPageShell from '@/components/agent/AgentPageShell.vue'
import AgentSidebar from '@/components/agent/AgentSidebar.vue'
import AgentContextRail from '@/components/agent/AgentContextRail.vue'
import AgentAssistantMessage from '@/components/agent/AgentAssistantMessage.vue'
import AgentReportPreviewModal from '@/components/agent/AgentReportPreviewModal.vue'
import { AGENT_UI } from '@/constants/agentUiText.js'

export default {
  name: 'AgentPageLayout',
  components: {
    AgentPageShell,
    AgentSidebar,
    AgentContextRail,
    AgentAssistantMessage,
    AgentReportPreviewModal,
  },
  mixins: [agentChatCore],
  props: {
    context: { type: Object, default: () => ({}) },
  },
  emits: ['visual-link-click'],
  data() {
    return {
      ui: AGENT_UI,
      pageSidebarOpen: true,
      pageRailOpen: typeof window !== 'undefined' ? window.innerWidth >= 1400 : false,
      layoutSynced: false,
      wasRailInline: typeof window !== 'undefined' ? window.innerWidth >= 1400 : false,
    }
  },
  mounted() {
    if (!this.sessionId) this.initSession()
    this.syncLayoutFromViewport()
    window.addEventListener('resize', this.onViewportResize)
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.onViewportResize)
  },
  methods: {
    ...mapActions(['openAgentPanel', 'syncDashboardFromAgentScope']),
    onViewportResize() {
      this.syncLayoutFromViewport()
    },
    syncLayoutFromViewport() {
      const wide = window.innerWidth >= 1400
      if (!this.layoutSynced) {
        this.pageRailOpen = wide
        this.layoutSynced = true
        this.wasRailInline = wide
        return
      }
      if (!wide) {
        this.pageRailOpen = false
      } else if (!this.wasRailInline) {
        this.pageRailOpen = true
      }
      this.wasRailInline = wide
    },
    async goDashboard() {
      await this.syncDashboardFromAgentScope()
      this.$router.push('/')
    },
    goFloatMode() {
      this.$router.push('/')
      this.openAgentPanel()
    },
  },
}
</script>

<style scoped lang="less">
@import './agent-page.less';
</style>
