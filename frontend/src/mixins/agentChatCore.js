import { mapActions, mapGetters } from 'vuex'
import {
  bootstrapAgentSession,
  createAgentSession,
  listAgentSkills,
  listAgentSessions,
  activateAgentSession,
  updateAgentSession,
  deleteAgentSession,
  postAgentMessage,
  resolveAgentApproval,
  cancelAgentJob,
  cancelAgentRun,
  postAgentDerive,
  listSessionRuns,
  JobAbortedError,
  createJobAbortHandle,
  fetchDeliverable,
  deliverableDownloadUrl,
} from '@/api/agent.js'
import {
  legacyToAssistantMessage,
  sessionMessagesToUi,
  recoveryHint,
  userMessage,
  createStreamingAssistantMessage,
  applyProgressToMessage,
  applyJobSessionMeta,
  mergeRunMetaIntoPayload,
  stripRunModifyBlock,
  enrichUiMessagesWithRuns,
} from '@/utils/agentAdapter.js'
import { AGENT_UI } from '@/constants/agentUiText.js'
import { isSkillSlashCommand, skillCommandLoadingText } from '@/utils/agentSlashCommands.js'
import {
  buildScopeAttachmentFromContext,
  cloneScopeAttachment,
  hasScopeContent,
  scopeAttachmentKey,
} from '@/utils/agentScopeAttachment.js'

export default {
  data() {
    return {
      messages: [],
      inputText: '',
      loading: false,
      loadingText: '思考中',
      sessionId: null,
      sessionTitle: '教师问答 Agent',
      permissionMode: 'analyze',
      sessions: [],
      sessionsLoading: false,
      todoItems: [],
      loadedSkills: [],
      pendingApproval: null,
      approvalResolver: null,
      revealTimerId: null,
      streamingMsgIndex: null,
      turnBaselineMsgCount: 0,
      pendingSendText: '',
      jobAbort: null,
      activeSendId: 0,
      autoScrollLocked: false,
      sampleQuestions: AGENT_UI.sampleQuestions,
      catalogSkills: [],
      scopeAttachmentDismissed: false,
      /** null = follow panel; object = local editable draft */
      scopeAttachmentDraft: null,
      _scopeAttachmentWatchKey: '',
      reportPreview: {
        open: false,
        loading: false,
        path: '',
        title: '',
        content: '',
        error: '',
      },
    }
  },
  created() {
    this.jobAbort = createJobAbortHandle()
  },
  computed: {
    messageCount() {
      return this.messages.length
    },
    composerScopeAttachment() {
      if (this.scopeAttachmentDismissed) return null
      if (this.scopeAttachmentDraft) {
        return hasScopeContent(this.scopeAttachmentDraft) ? this.scopeAttachmentDraft : null
      }
      return buildScopeAttachmentFromContext(this.context)
    },
  },
  watch: {
    context: {
      deep: true,
      immediate: true,
      handler(ctx) {
        const next = scopeAttachmentKey(buildScopeAttachmentFromContext(ctx))
        if (next !== this._scopeAttachmentWatchKey) {
          this._scopeAttachmentWatchKey = next
          this.scopeAttachmentDismissed = false
          this.scopeAttachmentDraft = null
        }
      },
    },
  },
  beforeUnmount() {
    this.clearRevealTimer()
  },
  methods: {
    ...mapActions(['syncNavScopeFromFilterContext']),
    recoveryHint,
    displaySteps(msg) {
      if (!msg || !msg.trace || !msg.trace.steps) return []
      return msg.trace.steps
    },
    onMessagesScroll() {
      const el = this.$refs.messagesEl
      if (!el) return
      const dist = el.scrollHeight - el.scrollTop - el.clientHeight
      this.autoScrollLocked = dist > 80
    },
    scrollToBottom() {
      if (this.autoScrollLocked) return
      this.$nextTick(() => {
        const el = this.$refs.messagesEl
        if (el) el.scrollTop = el.scrollHeight
      })
    },
    applyStreamingProgress(job) {
      if (!this.loading || this.streamingMsgIndex === null) return
      const msg = this.messages[this.streamingMsgIndex]
      if (!msg || !msg.streaming) return
      applyProgressToMessage(msg, job)
      applyJobSessionMeta(this, job?.progress)
      this.scrollToBottom()
    },
    async abortInFlightWork({ restoreComposer = false } = {}) {
      const hadWork =
        this.loading ||
        this.streamingMsgIndex !== null ||
        !!this.jobAbort?.getJobId?.()
      if (!hadWork) return

      this.activeSendId += 1
      this.jobAbort.abort()
      const jobId = this.jobAbort.getJobId()
      if (jobId) {
        try {
          await cancelAgentJob(jobId)
        } catch (err) {
          console.error('cancelAgentJob failed', err)
        }
      }
      this.discardInFlightTurn()
      if (restoreComposer && this.pendingSendText) {
        this.inputText = this.pendingSendText
        this.$nextTick(() => this.autoResizeComposer?.())
      }
      this.pendingApproval = null
      if (this.approvalResolver) {
        this.approvalResolver('deny')
        this.approvalResolver = null
      }
      this.loading = false
      this.loadingText = '思考中'
      this.pendingSendText = ''
      this.jobAbort.reset()
    },
    finalizeStreamingMessage(idx, res) {
      const msg = this.messages[idx]
      if (!msg) return
      const preservedMemory = msg.memory_saved
      let final = legacyToAssistantMessage(res)
      final = mergeRunMetaIntoPayload(final, msg)
      Object.assign(msg, final, { streaming: false, revealPhase: 1, statusHint: '', _runningTool: null })
      if (idx > 0 && Array.isArray(res?.messages)) {
        const lastUser = [...res.messages].reverse().find((m) => m.role === 'user')
        const userBubble = this.messages[idx - 1]
        if (lastUser && userBubble?.role === 'user') {
          userBubble.text = stripRunModifyBlock(lastUser.content || userBubble.text)
          if (lastUser.ui_scope) {
            userBubble.scopeAttachment = lastUser.ui_scope
          }
        }
      }
      if (
        Array.isArray(preservedMemory) &&
        preservedMemory.length &&
        !(final.memory_saved && final.memory_saved.length)
      ) {
        msg.memory_saved = preservedMemory
      }
      if (res?.filter_context) {
        this.syncNavScopeFromFilterContext(res.filter_context)
      }
      const links = final.report_links || []
      const canPreviewReport =
        final.goal_check?.is_satisfied !== false &&
        final.report_final_check?.ok !== false
      if (links.length && canPreviewReport) {
        const latest = links[links.length - 1]
        if (latest?.path && String(latest.path).toLowerCase().endsWith('.md')) {
          this.$nextTick(() => this.openReportPreview(latest))
        }
      }
    },
    revealPhase(msg) {
      if (msg.role !== 'assistant') return 5
      const p = msg.revealPhase
      return p === undefined ? 5 : p
    },
    summaryStatusText(summary) {
      if (!summary || !summary.overall_status) return ''
      const s = summary.overall_status
      if (s === 'complete') return '已完成分析'
      if (s === 'partial') return '部分完成'
      if (s === 'failed') return '分析失败'
      if (s === 'empty') return '暂无执行结果'
      return s
    },
    startRevealTimer(msgIndex) {
      this.clearRevealTimer()
      this.revealTimerId = setInterval(() => {
        const msg = this.messages[msgIndex]
        if (!msg || msg.role !== 'assistant') {
          this.clearRevealTimer()
          return
        }
        const next = (msg.revealPhase ?? 0) + 1
        if (next >= 5) this.clearRevealTimer()
        this.messages[msgIndex].revealPhase = Math.min(next, 5)
      }, 320)
    },
    clearRevealTimer() {
      if (this.revealTimerId) {
        clearInterval(this.revealTimerId)
        this.revealTimerId = null
      }
    },
    visualLinkLabel(link) {
      if (link.label) return link.label
      const view = link.view || 'View'
      const p = link.params
      const viewNames = {
        QuestionView: '题目分布',
        WeekView: '周趋势',
        StudentView: '建议关注学生',
        ScatterView: '散点分布',
        PortraitView: '画像',
      }
      const name = viewNames[view] || view
      let suffix = ''
      if (p && p.knowledge) suffix = `（${p.knowledge}）`
      else if (p && p.kind != null) suffix = `（簇 ${Number(p.kind) - 1}）`
      else if (p && p.cluster_id != null) suffix = `（cluster ${p.cluster_id}）`
      else if (p && Array.isArray(p.student_ids) && p.student_ids.length) suffix = '（学生）'
      return `查看${name}${suffix}`
    },
    onVisualLinkClick(link) {
      this.$emit('visual-link-click', { view: link.view, params: link.params || {} })
    },
    async openReportPreview(link) {
      const path = link?.path
      if (!path) return
      this.reportPreview = {
        open: true,
        loading: true,
        path,
        title: link.label || path,
        content: '',
        error: '',
      }
      try {
        const data = await fetchDeliverable(path)
        this.reportPreview.title = data.title || link.label || path
        this.reportPreview.content = data.content || ''
      } catch (err) {
        this.reportPreview.error = err.message || '报告加载失败'
      } finally {
        this.reportPreview.loading = false
      }
    },
    closeReportPreview() {
      this.reportPreview.open = false
    },
    downloadReport(link) {
      const path = link?.path || this.reportPreview.path
      if (!path) return
      window.open(deliverableDownloadUrl(path), '_blank')
    },
    fillSampleQuestion(q) {
      this.inputText = q
      this.$nextTick(() => this.autoResizeComposer?.())
    },
    fillSkillCommand(name) {
      this.inputText = name ? `/skill ${name}` : '/skill'
      this.$nextTick(() => this.autoResizeComposer?.())
    },
    async fetchCatalogSkills() {
      try {
        const data = await listAgentSkills()
        this.catalogSkills = data.skills || []
      } catch (err) {
        console.error('fetchCatalogSkills failed', err)
      }
    },
    onComposerKeydown(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        this.send()
      }
    },
    autoResizeComposer() {
      const el = this.$refs.composerEl
      if (!el) return
      el.style.height = 'auto'
      el.style.height = Math.min(el.scrollHeight, 160) + 'px'
    },
    async initSession() {
      this.sessionsLoading = true
      try {
        const session = await bootstrapAgentSession()
        await this.loadSessionWithRuns(session)
        await Promise.all([this.refreshSessions(), this.fetchCatalogSkills()])
      } catch (err) {
        console.error('initSession failed', err)
      } finally {
        this.sessionsLoading = false
      }
    },
    applySession(session, runs) {
      if (!session) return
      this.sessionId = session.id
      this.sessionTitle = session.title || '教师问答 Agent'
      this.permissionMode = session.permission_mode || 'analyze'
      this.todoItems = session.todo_items || []
      this.loadedSkills = session.loaded_skills || []
      let ui = sessionMessagesToUi(session.messages || [])
      if (Array.isArray(runs) && runs.length) {
        ui = enrichUiMessagesWithRuns(ui, runs)
      }
      this.messages = ui
      this.autoScrollLocked = false
      if (session.filter_context) {
        this.syncNavScopeFromFilterContext(session.filter_context)
      }
    },
    async loadSessionWithRuns(session) {
      if (!session?.id) return
      let runs = []
      try {
        const data = await listSessionRuns(session.id, 80)
        runs = data.runs || []
      } catch (err) {
        console.warn('listSessionRuns failed', err)
      }
      this.applySession(session, runs)
    },
    async refreshSessions() {
      try {
        const data = await listAgentSessions()
        this.sessions = data.sessions || []
      } catch (err) {
        console.error('refreshSessions failed', err)
      }
    },
    async createNewSession() {
      try {
        await this.abortInFlightWork({ restoreComposer: false })
        const session = await createAgentSession({ permission_mode: this.permissionMode })
        await this.loadSessionWithRuns(session)
        this.messages = []
        this.todoItems = session.todo_items || []
        this.loadedSkills = session.loaded_skills || []
        await this.refreshSessions()
      } catch (err) {
        console.error('createNewSession failed', err)
      }
    },
    async switchSession(sessionId) {
      if (!sessionId || sessionId === this.sessionId) return
      try {
        await this.abortInFlightWork({ restoreComposer: false })
        const session = await activateAgentSession(sessionId)
        await this.loadSessionWithRuns(session)
      } catch (err) {
        console.error('switchSession failed', err)
      }
    },
    async renameSession(title) {
      if (!this.sessionId || !title) return
      try {
        const session = await updateAgentSession(this.sessionId, { title })
        await this.loadSessionWithRuns(session)
        await this.refreshSessions()
      } catch (err) {
        console.error('renameSession failed', err)
      }
    },
    async renameSessionFromList({ id, title }) {
      if (!id || !title) return
      try {
        await updateAgentSession(id, { title })
        if (id === this.sessionId) this.sessionTitle = title
        await this.refreshSessions()
      } catch (err) {
        console.error('renameSessionFromList failed', err)
      }
    },
    async deleteSession(id) {
      if (!id) return
      try {
        await deleteAgentSession(id)
        await this.refreshSessions()
        if (id !== this.sessionId) return
        const next = this.sessions[0]
        if (next) await this.switchSession(next.id)
        else await this.createNewSession()
      } catch (err) {
        console.error('deleteSession failed', err)
      }
    },
    async onModeChange() {
      if (!this.sessionId) return
      try {
        const session = await updateAgentSession(this.sessionId, {
          permission_mode: this.permissionMode,
        })
        await this.loadSessionWithRuns(session)
      } catch (err) {
        console.error('onModeChange failed', err)
      }
    },
    async onRailModeChange(mode) {
      this.permissionMode = mode
      await this.onModeChange()
    },
    formatApprovalParams(params) {
      try {
        return JSON.stringify(params || {}, null, 2)
      } catch (e) {
        return String(params || '')
      }
    },
    waitForApproval(approval) {
      return new Promise((resolve) => {
        this.pendingApproval = approval
        this.loadingText = '等待权限确认'
        this.approvalResolver = resolve
      })
    },
    async resolveApproval(decision) {
      if (!this.pendingApproval) return
      const approvalId = this.pendingApproval.id
      this.pendingApproval = null
      this.loadingText = '继续执行'
      try {
        await resolveAgentApproval(approvalId, decision, decision === 'allow_always')
      } catch (err) {
        console.error('resolveApproval failed', err)
      }
      if (this.approvalResolver) {
        this.approvalResolver(decision)
        this.approvalResolver = null
      }
    },
    discardInFlightTurn() {
      const keep = Math.max(0, this.turnBaselineMsgCount || 0)
      if (this.messages.length > keep) {
        this.messages.splice(keep)
      }
      this.streamingMsgIndex = null
      this.clearRevealTimer()
    },
    async stopTurn() {
      if (!this.loading) return
      await this.abortInFlightWork({ restoreComposer: true })
    },
    async onCancelToolRun(runId) {
      if (!runId) return
      try {
        await cancelAgentRun(runId)
      } catch (err) {
        console.error('cancelAgentRun failed', err)
      }
    },
    async onDeriveToolRun(step) {
      if (!this.sessionId || !step?.run_id || this.loading) return
      const message = window.prompt(
        '描述要如何修改（例如：改成按周汇总）',
        '改成按周汇总',
      )
      if (!message || !String(message).trim()) return
      await this.startDerivedTurn(step.run_id, String(message).trim())
    },
    async startDerivedTurn(runId, message) {
      this.clearRevealTimer()
      const sendId = this.activeSendId + 1
      this.activeSendId = sendId
      this.jobAbort.reset()
      this.pendingSendText = message
      this.turnBaselineMsgCount = this.messages.length
      this.autoScrollLocked = false
      this.messages.push(userMessage(message))
      const streamIdx = this.messages.length
      this.messages.push(createStreamingAssistantMessage())
      this.streamingMsgIndex = streamIdx
      this.loading = true
      this.loadingText = '正在基于上次结果修改…'
      this.scrollToBottom()
      try {
        const res = await postAgentDerive(this.sessionId, runId, { message }, {
          onApproval: (approval) => this.waitForApproval(approval),
          onProgress: (job) => this.applyStreamingProgress(job),
          shouldAbort: () => this.jobAbort.isAborted(),
          onJobStarted: (jobId) => this.jobAbort.setJobId(jobId),
        })
        if (sendId !== this.activeSendId) return
        if (res.session_title) this.sessionTitle = res.session_title
        if (res.permission_mode) this.permissionMode = res.permission_mode
        if (Array.isArray(res.todo_items)) this.todoItems = res.todo_items
        if (Array.isArray(res.loaded_skills)) this.loadedSkills = res.loaded_skills
        this.finalizeStreamingMessage(streamIdx, res)
        await this.refreshSessions()
        this.$nextTick(() => {
          this.startRevealTimer(streamIdx)
          this.scrollToBottom()
        })
      } catch (err) {
        if (sendId !== this.activeSendId) return
        if (err instanceof JobAbortedError || this.jobAbort.isAborted()) {
          this.discardInFlightTurn()
        } else if (this.streamingMsgIndex !== null) {
          Object.assign(this.messages[this.streamingMsgIndex], {
            answer: err.message || '修改请求失败，请稍后重试。',
            streaming: false,
            revealPhase: 5,
            trace: this.messages[this.streamingMsgIndex].trace || { steps: [] },
            closing: '',
          })
        }
      } finally {
        if (sendId !== this.activeSendId) return
        this.pendingApproval = null
        this.approvalResolver = null
        this.streamingMsgIndex = null
        this.pendingSendText = ''
        this.jobAbort.reset()
        this.loading = false
        this.loadingText = '思考中'
      }
    },
    async send() {
      const text = (this.inputText || '').trim()
      if (!text || this.loading || !this.sessionId) return
      this.clearRevealTimer()
      const sendId = this.activeSendId + 1
      this.activeSendId = sendId
      this.jobAbort.reset()
      this.pendingSendText = text
      this.turnBaselineMsgCount = this.messages.length
      this.inputText = ''
      this.autoScrollLocked = false
      const scopeAttachment = this.composerScopeAttachment
        ? { ...this.composerScopeAttachment }
        : null
      const sendContext = this.buildSendContext(scopeAttachment)
      this.messages.push(userMessage(text, scopeAttachment))
      const streamIdx = this.messages.length
      this.messages.push(createStreamingAssistantMessage())
      this.streamingMsgIndex = streamIdx
      this.loading = true
      this.loadingText = isSkillSlashCommand(text)
        ? skillCommandLoadingText(text)
        : '思考中'
      this.scrollToBottom()
      try {
        const res = await postAgentMessage(this.sessionId, text, sendContext, {
          onApproval: (approval) => this.waitForApproval(approval),
          onProgress: (job) => this.applyStreamingProgress(job),
          shouldAbort: () => this.jobAbort.isAborted(),
          onJobStarted: (jobId) => this.jobAbort.setJobId(jobId),
        })
        if (sendId !== this.activeSendId) return
        if (res.session_title) this.sessionTitle = res.session_title
        if (res.permission_mode) this.permissionMode = res.permission_mode
        if (Array.isArray(res.todo_items)) this.todoItems = res.todo_items
        if (Array.isArray(res.loaded_skills)) this.loadedSkills = res.loaded_skills
        this.finalizeStreamingMessage(streamIdx, res)
        await this.refreshSessions()
        this.$nextTick(() => {
          this.startRevealTimer(streamIdx)
          this.scrollToBottom()
        })
      } catch (err) {
        if (sendId !== this.activeSendId) return
        if (err instanceof JobAbortedError || this.jobAbort.isAborted()) {
          this.discardInFlightTurn()
          if (this.pendingSendText) {
            this.inputText = this.pendingSendText
            this.$nextTick(() => this.autoResizeComposer?.())
          }
        } else if (this.streamingMsgIndex !== null) {
          Object.assign(this.messages[this.streamingMsgIndex], {
            answer: err.message || '请求失败，请稍后重试。',
            streaming: false,
            revealPhase: 5,
            trace: this.messages[this.streamingMsgIndex].trace || { steps: [] },
            closing: '',
          })
        } else {
          this.messages.push({
            role: 'assistant',
            answer: err.message || '请求失败，请稍后重试。',
            evidence: [],
            actions: [],
            visual_links: [],
            trace: null,
            goal_check: null,
            summary: null,
            revealPhase: 5,
          })
        }
      } finally {
        if (sendId !== this.activeSendId) return
        this.pendingApproval = null
        this.approvalResolver = null
        this.streamingMsgIndex = null
        this.pendingSendText = ''
        this.jobAbort.reset()
        this.loading = false
        this.loadingText = '思考中'
      }
    },
    buildSendContext(scopeAttachment) {
      const base = { ...(this.context || {}) }
      if (scopeAttachment && hasScopeContent(scopeAttachment)) {
        base.selected_student_ids = [...(scopeAttachment.selected_student_ids || [])]
        base.classes = [...(scopeAttachment.classes || [])]
        base.majors = [...(scopeAttachment.majors || [])]
        if (Array.isArray(scopeAttachment.week_range) && scopeAttachment.week_range.length >= 2) {
          base.week_range = [...scopeAttachment.week_range]
        } else {
          base.week_range = undefined
        }
        base.ui_scope = { ...scopeAttachment }
      } else {
        base.selected_student_ids = []
        base.classes = []
        base.majors = []
        base.week_range = undefined
        base.ui_scope = null
      }
      return base
    },
    ensureScopeAttachmentDraft() {
      if (this.scopeAttachmentDraft) return
      const fromCtx = buildScopeAttachmentFromContext(this.context)
      this.scopeAttachmentDraft = cloneScopeAttachment(fromCtx) || {
        selected_student_ids: [],
        classes: [],
        majors: [],
      }
    },
    pruneScopeAttachmentDraft() {
      if (!this.scopeAttachmentDraft) return
      if (!hasScopeContent(this.scopeAttachmentDraft)) {
        this.scopeAttachmentDraft = null
        this.scopeAttachmentDismissed = true
      }
    },
    dismissComposerScopeAttachment() {
      this.scopeAttachmentDismissed = true
      this.scopeAttachmentDraft = {
        selected_student_ids: [],
        classes: [],
        majors: [],
      }
    },
    removeComposerScopeStudent(studentId) {
      const sid = String(studentId || '').trim()
      if (!sid) return
      this.ensureScopeAttachmentDraft()
      const ids = this.scopeAttachmentDraft.selected_student_ids || []
      this.scopeAttachmentDraft = {
        ...this.scopeAttachmentDraft,
        selected_student_ids: ids.filter((id) => id !== sid),
      }
      this.pruneScopeAttachmentDraft()
    },
    removeComposerScopeClass(className) {
      const name = String(className || '').trim()
      if (!name) return
      this.ensureScopeAttachmentDraft()
      const classes = this.scopeAttachmentDraft.classes || []
      this.scopeAttachmentDraft = {
        ...this.scopeAttachmentDraft,
        classes: classes.filter((c) => c !== name),
      }
      this.pruneScopeAttachmentDraft()
    },
    removeComposerScopeMajor(major) {
      const name = String(major || '').trim()
      if (!name) return
      this.ensureScopeAttachmentDraft()
      const majors = this.scopeAttachmentDraft.majors || []
      this.scopeAttachmentDraft = {
        ...this.scopeAttachmentDraft,
        majors: majors.filter((m) => m !== name),
      }
      this.pruneScopeAttachmentDraft()
    },
    removeComposerScopeWeek() {
      this.ensureScopeAttachmentDraft()
      const next = { ...this.scopeAttachmentDraft }
      delete next.week_range
      this.scopeAttachmentDraft = next
      this.pruneScopeAttachmentDraft()
    },
  },
}
