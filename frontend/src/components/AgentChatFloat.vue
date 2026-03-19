<template>
  <div v-if="visible" class="agent-float-root">
    <!-- 最小化时只显示右下角小入口 -->
    <div
      v-if="minimized"
      class="agent-pill"
      @click="$emit('expand')"
    >
      Agent
    </div>

    <!-- 展开时的完整浮层：支持拖拽移动 + 右下角调整大小 -->
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
        @mousedown="startDrag"
      >
        <span class="agent-panel-title">教师问答 Agent</span>
        <div class="agent-panel-actions">
          <button type="button" class="btn-icon" title="最小化" @click.stop="$emit('minimize')">−</button>
          <button type="button" class="btn-icon" title="关闭" @click.stop="$emit('close')">×</button>
        </div>
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
              <div class="agent-msg-bubble agent-msg-bubble--assistant">
                <div v-if="revealPhase(msg) >= 0" class="agent-answer agent-reveal">{{ msg.answer }}</div>
                <!-- 结果状态区：goal_check + summary -->
                <div v-if="revealPhase(msg) >= 1 && (msg.goal_check || msg.summary)" class="agent-status-block agent-reveal">
                  <div class="agent-section-label">结果状态</div>
                  <div v-if="msg.goal_check" class="agent-goal-check" :class="{ 'agent-goal-check--satisfied': msg.goal_check.is_satisfied }">
                    <template v-if="msg.goal_check.is_satisfied">本次回答已满足你的问题</template>
                    <template v-else-if="msg.goal_check.is_pending_clarification">
                      请按上方提示补充信息
                      <span v-if="msg.goal_check.reason" class="agent-goal-check-reason">（{{ msg.goal_check.reason }}）</span>
                    </template>
                    <template v-else>
                      当前回答可能不完整
                      <span v-if="msg.goal_check.reason" class="agent-goal-check-reason">（{{ msg.goal_check.reason }}）</span>
                    </template>
                  </div>
                  <div v-if="msg.summary" class="agent-summary-status">
                    {{ summaryStatusText(msg.summary) }}
                  </div>
                  <div v-if="msg.summary && msg.summary.key_findings && msg.summary.key_findings.length" class="agent-key-findings">
                    <span class="agent-key-findings-label">关键结论：</span>
                    <ul>
                      <li v-for="(f, fi) in msg.summary.key_findings.slice(0, 3)" :key="fi">{{ f }}</li>
                    </ul>
                  </div>
                  <div v-if="msg.summary && msg.summary.unresolved_points && msg.summary.unresolved_points.length" class="agent-unresolved">
                    <span class="agent-unresolved-label">未解决：</span>
                    <ul>
                      <li v-for="(u, ui) in msg.summary.unresolved_points" :key="ui">{{ u }}</li>
                    </ul>
                  </div>
                </div>
                <div v-if="revealPhase(msg) >= 2 && msg.evidence && msg.evidence.length" class="agent-evidence agent-reveal">
                  <div class="agent-section-label">依据</div>
                  <div
                    v-for="(e, i) in msg.evidence"
                    :key="i"
                    class="agent-evidence-item agent-stagger"
                    :style="{ animationDelay: (i * 0.06) + 's' }"
                  >
                    <span class="agent-evidence-tool">{{ e.tool }}</span>
                    <span class="agent-evidence-summary">{{ e.summary }}</span>
                  </div>
                </div>
                <div v-if="revealPhase(msg) >= 3 && msg.actions && msg.actions.length" class="agent-actions agent-reveal">
                  <div class="agent-section-label">建议</div>
                  <ul>
                    <li
                      v-for="(a, i) in msg.actions"
                      :key="i"
                      class="agent-stagger"
                      :style="{ animationDelay: (i * 0.06) + 's' }"
                    >{{ a }}</li>
                  </ul>
                </div>
                <div v-if="revealPhase(msg) >= 4 && msg.visual_links && msg.visual_links.length" class="agent-visual-links agent-reveal">
                  <div class="agent-section-label">图表入口</div>
                  <button
                    v-for="(link, i) in msg.visual_links"
                    :key="i"
                    type="button"
                    class="agent-visual-link-btn agent-stagger"
                    :style="{ animationDelay: (i * 0.08) + 's' }"
                    @click="onVisualLinkClick(link)"
                  >
                    {{ visualLinkLabel(link) }}
                  </button>
                </div>
              </div>
            </template>
          </div>
          <div v-if="loading" class="agent-msg agent-msg--assistant">
            <div class="agent-msg-bubble agent-msg-bubble--assistant agent-loading">
              <span class="agent-loading-dots">思考中</span><span class="agent-loading-dots-anim">…</span>
            </div>
          </div>
        </div>

        <!-- 可折叠运行轨迹 -->
        <div class="agent-trace">
          <button
            type="button"
            class="agent-trace-toggle"
            @click="traceOpen = !traceOpen"
          >
            {{ traceOpen ? '收起' : '查看本次调用轨迹' }}
          </button>
          <Transition name="trace-fade">
            <div v-show="traceOpen" class="agent-trace-content">
              <template v-if="lastTrace && lastTrace.steps && lastTrace.steps.length">
                <div
                  v-for="(step, i) in lastTrace.steps"
                  :key="i"
                  class="agent-trace-step"
                  :class="{ 'agent-trace-step--expanded': expandedTraceStepIndex === i }"
                >
                  <button
                    type="button"
                    class="agent-trace-step-header"
                    @click="toggleTraceStep(i)"
                  >
                    <span class="agent-trace-tool">第 {{ i + 1 }} 步：{{ step.tool }}</span>
                    <span v-if="step.summary" class="agent-trace-summary-inline">{{ step.summary }}</span>
                    <span v-if="step.status" class="agent-trace-status" :class="'agent-trace-status--' + (step.status || '')">{{ step.status }}</span>
                    <span v-if="step.duration_ms" class="agent-trace-duration">{{ step.duration_ms }}ms</span>
                    <span class="agent-trace-expand-icon">{{ expandedTraceStepIndex === i ? '▼' : '▶' }}</span>
                  </button>
                  <div v-show="expandedTraceStepIndex === i" class="agent-trace-step-detail">
                    <div v-if="step.reason" class="agent-trace-detail-row"><span class="agent-trace-detail-label">原因</span> {{ step.reason }}</div>
                    <div v-if="step.params && Object.keys(step.params).length" class="agent-trace-detail-row"><span class="agent-trace-detail-label">参数</span> <pre class="agent-trace-params-pre">{{ JSON.stringify(step.params, null, 2) }}</pre></div>
                    <div v-if="step.coverage && Object.keys(step.coverage).length" class="agent-trace-detail-row"><span class="agent-trace-detail-label">覆盖</span> {{ JSON.stringify(step.coverage) }}</div>
                    <div v-if="step.quality && Object.keys(step.quality).length" class="agent-trace-detail-row"><span class="agent-trace-detail-label">质量</span> {{ JSON.stringify(step.quality) }}</div>
                    <div v-if="step.error" class="agent-trace-detail-row agent-trace-detail-error"><span class="agent-trace-detail-label">错误</span> {{ step.error }}</div>
                  </div>
                </div>
              </template>
              <div v-else class="agent-trace-empty">暂无轨迹</div>
            </div>
          </Transition>
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
          <button type="button" class="agent-send" :disabled="loading" @click="send">发送</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import { postAgentQuery } from '@/api/agent.js'

export default {
  name: 'AgentChatFloat',
  props: {
    visible: { type: Boolean, default: false },
    minimized: { type: Boolean, default: false },
    context: {
      type: Object,
      default: () => ({}),
    },
  },
  computed: {
    ...mapGetters(['getAgentJumpFeedback']),
  },
  data() {
    return {
      messages: [],
      inputText: '',
      loading: false,
      traceOpen: false,
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
      expandedTraceStepIndex: null,
    }
  },
  beforeUnmount() {
    this.clearRevealTimer()
  },
  computed: {
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
    lastTrace() {
      for (let i = this.messages.length - 1; i >= 0; i--) {
        if (this.messages[i].role === 'assistant' && this.messages[i].trace) {
          return this.messages[i].trace
        }
      }
      return null
    },
  },
  methods: {
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
      else if (p && p.cluster_id != null) suffix = `（cluster ${p.cluster_id}）`
      else if (p && Array.isArray(p.student_ids) && p.student_ids.length) suffix = '（学生）'
      return `查看${name}${suffix}`
    },
    onVisualLinkClick(link) {
      this.$emit('visual-link-click', { view: link.view, params: link.params || {} })
    },
    toggleTraceStep(stepIndex) {
      this.expandedTraceStepIndex = this.expandedTraceStepIndex === stepIndex ? null : stepIndex
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
    async send() {
      const text = (this.inputText || '').trim()
      if (!text || this.loading) return
      this.clearRevealTimer()
      this.inputText = ''
      this.messages.push({ role: 'user', text })
      this.loading = true
      try {
        const res = await postAgentQuery(text, this.context)
        const idx = this.messages.length
        this.messages.push({
          role: 'assistant',
          answer: res.answer || '',
          evidence: res.evidence || [],
          actions: res.actions || [],
          visual_links: res.visual_links || [],
          trace: res.trace,
          goal_check: res.goal_check || null,
          summary: res.summary || null,
          revealPhase: 0,
        })
        this.traceOpen = !!res.trace
        this.expandedTraceStepIndex = null
        this.$nextTick(() => {
          this.startRevealTimer(idx)
          const el = this.$refs.messagesEl
          if (el) el.scrollTop = el.scrollHeight
        })
      } catch (err) {
        this.messages.push({
          role: 'assistant',
          answer: '请求失败，请稍后重试。',
          evidence: [],
          actions: [],
          visual_links: [],
          trace: null,
          goal_check: null,
          summary: null,
          revealPhase: 5,
        })
      } finally {
        this.loading = false
      }
    },
  },
}
</script>

<style scoped lang="less">
.agent-float-root {
  position: fixed;
  z-index: 1000;
  pointer-events: none;
  & > * {
    pointer-events: auto;
  }
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
</style>
