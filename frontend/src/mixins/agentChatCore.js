import { mapActions, mapGetters } from 'vuex'
import {
  bootstrapAgentSession,
  createAgentSession,
  listAgentSessions,
  activateAgentSession,
  updateAgentSession,
  deleteAgentSession,
  postAgentMessage,
  resolveAgentApproval,
  cancelAgentJob,
  JobAbortedError,
  createJobAbortHandle,
} from '@/api/agent.js'
import {
  legacyToAssistantMessage,
  sessionMessagesToUi,
  recoveryHint,
  userMessage,
  createStreamingAssistantMessage,
  applyProgressToMessage,
} from '@/utils/agentAdapter.js'
import { AGENT_UI } from '@/constants/agentUiText.js'

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
    }
  },
  created() {
    this.jobAbort = createJobAbortHandle()
  },
  computed: {
    messageCount() {
      return this.messages.length
    },
  },
  beforeUnmount() {
    this.clearRevealTimer()
  },
  methods: {
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
      if (this.streamingMsgIndex === null) return
      const msg = this.messages[this.streamingMsgIndex]
      if (!msg) return
      applyProgressToMessage(msg, job)
      this.scrollToBottom()
    },
    finalizeStreamingMessage(idx, res) {
      const msg = this.messages[idx]
      if (!msg) return
      const final = legacyToAssistantMessage(res)
      Object.assign(msg, final, { streaming: false, revealPhase: 1, statusHint: '' })
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
    fillSampleQuestion(q) {
      this.inputText = q
      this.$nextTick(() => this.autoResizeComposer?.())
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
        this.applySession(session)
        await this.refreshSessions()
      } catch (err) {
        console.error('initSession failed', err)
      } finally {
        this.sessionsLoading = false
      }
    },
    applySession(session) {
      if (!session) return
      this.sessionId = session.id
      this.sessionTitle = session.title || '教师问答 Agent'
      this.permissionMode = session.permission_mode || 'analyze'
      this.todoItems = session.todo_items || []
      this.messages = sessionMessagesToUi(session.messages || [])
      this.autoScrollLocked = false
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
        const session = await createAgentSession({ permission_mode: this.permissionMode })
        this.applySession(session)
        this.messages = []
        await this.refreshSessions()
      } catch (err) {
        console.error('createNewSession failed', err)
      }
    },
    async switchSession(sessionId) {
      if (!sessionId || sessionId === this.sessionId) return
      try {
        const session = await activateAgentSession(sessionId)
        this.applySession(session)
      } catch (err) {
        console.error('switchSession failed', err)
      }
    },
    async renameSession(title) {
      if (!this.sessionId || !title) return
      try {
        const session = await updateAgentSession(this.sessionId, { title })
        this.applySession(session)
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
        this.applySession(session)
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
      if (this.pendingSendText) {
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
      this.messages.push(userMessage(text))
      const streamIdx = this.messages.length
      this.messages.push(createStreamingAssistantMessage())
      this.streamingMsgIndex = streamIdx
      this.loading = true
      this.loadingText = '思考中'
      this.scrollToBottom()
      try {
        const res = await postAgentMessage(this.sessionId, text, this.context, {
          onApproval: (approval) => this.waitForApproval(approval),
          onProgress: (job) => this.applyStreamingProgress(job),
          shouldAbort: () => this.jobAbort.isAborted(),
          onJobStarted: (jobId) => this.jobAbort.setJobId(jobId),
        })
        if (sendId !== this.activeSendId) return
        if (res.session_title) this.sessionTitle = res.session_title
        if (res.permission_mode) this.permissionMode = res.permission_mode
        if (res.todo_items) this.todoItems = res.todo_items
        if (res.loaded_skills) this.loadedSkills = res.loaded_skills
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
  },
}
