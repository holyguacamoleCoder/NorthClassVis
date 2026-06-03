<template>
  <div class="agent-msg-bubble agent-msg-bubble--assistant agent-msg-bubble--enter">
    <div
      v-if="msg.streaming && msg.statusHint && !hasAnyContent(msg)"
      class="agent-stream-hint"
    >
      {{ msg.statusHint }}
    </div>

    <!-- ① 计划段 -->
    <div v-if="showPlan(msg)" class="agent-plan-block">
      <div class="agent-section-label">{{ ui.sectionPlan }}</div>
      <AgentStreamingMarkdown
        v-if="msg.streaming && msg.thinking"
        :source="msg.thinking"
        :active="true"
        class="agent-thinking-md"
      />
      <AgentMarkdown
        v-else-if="msg.thinking"
        :source="msg.thinking"
        class="agent-thinking-md"
      />
    </div>

    <!-- ② 过程段（timeline 穿插） -->
    <AgentProcessTimeline
      v-if="showProcess(msg)"
      :items="processItems(msg)"
      :running-tool="msg.streaming ? runningTool : null"
      :streaming="!!msg.streaming"
      :default-expanded="processDefaultExpanded(msg)"
      :run-actions-enabled="!loading || !!msg.streaming"
      @cancel-run="$emit('cancel-run', $event)"
      @derive-run="$emit('derive-run', $event)"
    />

    <!-- ③ 结论段 -->
    <div v-if="showConclusion(msg)" class="agent-conclusion-block">
      <div class="agent-section-label">{{ ui.sectionConclusion }}</div>
      <AgentStreamingMarkdown
        v-if="msg.streaming && msg.answer"
        :source="displayAnswer(msg)"
        :active="true"
        class="agent-answer-md"
        @link-click="onMarkdownLinkClick"
        @report-link-click="onReportLinkClick"
      />
      <AgentMarkdown
        v-else-if="revealPhase(msg) >= 1 && msg.answer"
        :source="displayAnswer(msg)"
        class="agent-reveal agent-answer-md"
        @link-click="onMarkdownLinkClick"
        @report-link-click="onReportLinkClick"
      />
      <AgentStreamingMarkdown
        v-if="msg.streaming && msg.closing"
        :source="displayClosing(msg)"
        :active="true"
        class="agent-closing-md"
        @link-click="onMarkdownLinkClick"
        @report-link-click="onReportLinkClick"
      />
      <AgentMarkdown
        v-else-if="revealPhase(msg) >= 1 && msg.closing"
        :source="displayClosing(msg)"
        class="agent-reveal agent-closing-md"
        @link-click="onMarkdownLinkClick"
        @report-link-click="onReportLinkClick"
      />
    </div>

    <div v-if="msg.continue_reason && recoveryHint(msg.continue_reason)" class="agent-recovery-hint agent-reveal">
      {{ recoveryHint(msg.continue_reason) }}
    </div>
    <div v-if="revealPhase(msg) >= 2 && (msg.goal_check || msg.summary)" class="agent-status-block agent-reveal">
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
      <div v-if="msg.summary" class="agent-summary-status">{{ summaryStatusText(msg.summary) }}</div>
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
    <div v-if="revealPhase(msg) >= 3 && msg.actions && msg.actions.length" class="agent-actions agent-reveal">
      <div class="agent-section-label">建议</div>
      <ul>
        <li v-for="(a, i) in msg.actions" :key="i" class="agent-stagger">{{ a }}</li>
      </ul>
    </div>
    <AgentDeliverableLinks
      v-if="showReportLinks(msg)"
      class="agent-reveal"
      :links="msg.report_links"
      @preview="$emit('report-preview', $event)"
      @download="$emit('report-download', $event)"
    />
    <AgentMemorySaved
      v-if="showMemorySaved(msg)"
      class="agent-reveal"
      :items="msg.memory_saved"
    />
    <div
      v-if="showVisualLinks(msg)"
      class="agent-visual-links agent-reveal"
    >
      <div class="agent-section-label">图表入口</div>
      <button
        v-for="(link, i) in msg.visual_links"
        :key="i"
        type="button"
        class="agent-visual-link-btn"
        @click="$emit('visual-link-click', link)"
      >{{ visualLinkLabel(link) }}</button>
    </div>
  </div>
</template>

<script>
import AgentMarkdown from '@/components/agent/AgentMarkdown.vue'
import AgentStreamingMarkdown from '@/components/agent/AgentStreamingMarkdown.vue'
import AgentProcessTimeline from '@/components/agent/AgentProcessTimeline.vue'
import AgentDeliverableLinks from '@/components/agent/AgentDeliverableLinks.vue'
import AgentMemorySaved from '@/components/agent/AgentMemorySaved.vue'
import { AGENT_UI } from '@/constants/agentUiText.js'
import { processTimelineItems, processTimelineStats } from '@/utils/agentTimeline.js'
import { stripVisualLinkMarkdown, findVisualLinkFromMarkdownClick } from '@/utils/visualLinks.js'
import { stripReportLinkMarkdown, findReportLinkFromMarkdownClick } from '@/utils/reportLinks.js'

export default {
  name: 'AgentAssistantMessage',
  components: {
    AgentMarkdown,
    AgentStreamingMarkdown,
    AgentProcessTimeline,
    AgentDeliverableLinks,
    AgentMemorySaved,
  },
  props: {
    msg: { type: Object, required: true },
    displaySteps: { type: Function, required: true },
    revealPhase: { type: Function, required: true },
    recoveryHint: { type: Function, required: true },
    summaryStatusText: { type: Function, required: true },
    visualLinkLabel: { type: Function, required: true },
    runningTool: { type: Object, default: null },
    loading: { type: Boolean, default: false },
  },
  emits: ['visual-link-click', 'report-preview', 'report-download', 'cancel-run', 'derive-run'],
  data() {
    return { ui: AGENT_UI }
  },
  methods: {
    processItems(msg) {
      return processTimelineItems(msg)
    },
    hasAnyContent(msg) {
      return (
        (msg.thinking && msg.thinking.trim()) ||
        (msg.answer && msg.answer.trim()) ||
        (msg.closing && msg.closing.trim()) ||
        this.processItems(msg).length > 0
      )
    },
    showPlan(msg) {
      const text = (msg.thinking || '').trim()
      if (!text) return false
      if (msg.streaming) return true
      return this.revealPhase(msg) >= 1
    },
    showProcess(msg) {
      if (this.processItems(msg).length) return true
      if (msg.streaming && this.runningTool) return true
      return false
    },
    processDefaultExpanded(msg) {
      const { failed } = processTimelineStats(this.processItems(msg))
      return failed > 0 || !!msg.streaming
    },
    showConclusion(msg) {
      const has = (msg.answer && msg.answer.trim()) || (msg.closing && msg.closing.trim())
      if (!has) return false
      if (msg.streaming) return true
      return this.revealPhase(msg) >= 1
    },
    displayAnswer(msg) {
      return this.stripNarrativeMarkdown(msg.answer || '', msg)
    },
    displayClosing(msg) {
      return this.stripNarrativeMarkdown(msg.closing || '', msg)
    },
    stripNarrativeMarkdown(text, msg) {
      const hasLinks = (msg.visual_links || []).length > 0
      const hasReports = (msg.report_links || []).length > 0
      const hasFakeSection = /\n#{1,3}\s*可点击入口/i.test(text)
      let out = stripVisualLinkMarkdown(text, hasLinks || hasFakeSection)
      out = stripReportLinkMarkdown(out, hasReports || hasFakeSection)
      return out
    },
    showReportLinks(msg) {
      if (msg.streaming) return false
      const links = msg.report_links || []
      if (!links.length) return false
      return this.revealPhase(msg) >= 1
    },
    showMemorySaved(msg) {
      if (msg.streaming) return false
      const items = msg.memory_saved || []
      if (!items.length) return false
      return this.revealPhase(msg) >= 1
    },
    showVisualLinks(msg) {
      if (msg.streaming) return false
      const links = msg.visual_links || []
      if (!links.length) return false
      return this.revealPhase(msg) >= 1
    },
    onMarkdownLinkClick(href) {
      const report = findReportLinkFromMarkdownClick(href, this.msg.report_links)
      if (report) {
        this.$emit('report-preview', report)
        return
      }
      const link = findVisualLinkFromMarkdownClick(href, this.msg.visual_links)
      if (link) this.$emit('visual-link-click', link)
    },
    onReportLinkClick(link) {
      if (link) this.$emit('report-preview', link)
    },
  },
}
</script>

<style scoped lang="less">
.agent-plan-block {
  margin-bottom: 10px;
  padding: 8px 10px;
  background: rgba(55, 126, 184, 0.06);
  border-left: 3px solid #377eb8;
  border-radius: 4px;
}
.agent-conclusion-block {
  margin-top: 10px;
  padding-top: 4px;
}
.agent-thinking-md,
.agent-answer-md,
.agent-closing-md {
  margin-top: 4px;
  font-size: 14px;
}
.agent-thinking-md { color: #444; }
.agent-stream-hint {
  font-size: 13px;
  color: #666;
  margin-bottom: 10px;
  padding: 8px 10px;
  background: rgba(0, 0, 0, 0.04);
  border-radius: 6px;
}
.agent-status-block {
  margin: 10px 0;
  padding: 8px 10px;
  background: #f8f9fa;
  border-radius: 6px;
  font-size: 14px;
}
.agent-goal-check { color: #856404; margin-bottom: 4px; }
.agent-goal-check--satisfied { color: #155724; }
.agent-goal-check-reason { color: #666; font-size: 12px; }
.agent-summary-status { color: #666; margin-bottom: 6px; }
.agent-key-findings, .agent-unresolved { margin-top: 6px; font-size: 13px; }
.agent-key-findings-label, .agent-unresolved-label { font-weight: 600; color: #333; }
.agent-unresolved ul { color: #721c24; margin: 2px 0 0; padding-left: 18px; }
.agent-key-findings ul { margin: 2px 0 0; padding-left: 18px; }
.agent-section-label { font-size: 13px; color: #666; margin: 10px 0 6px; font-weight: 600; }
.agent-actions ul { margin: 0; padding-left: 20px; font-size: 14px; line-height: 1.5; }
.agent-visual-links { margin-top: 10px; }
.agent-visual-link-btn {
  display: block;
  width: 100%;
  margin-top: 8px;
  padding: 8px 12px;
  text-align: left;
  font-size: 14px;
  border: 1px solid #377eb8;
  border-radius: 6px;
  background: #f0f6fc;
  color: #1a5a8a;
  cursor: pointer;
  &:hover { background: #e3eef8; border-color: #2a6294; }
}
.agent-recovery-hint {
  margin-top: 8px;
  padding: 8px 10px;
  background: #fff3cd;
  color: #856404;
  border-radius: 4px;
  font-size: 13px;
}
.agent-reveal { animation: agent-fade-in 0.35s ease-out forwards; }
.agent-stagger { animation: agent-fade-in 0.3s ease-out backwards; }
@keyframes agent-fade-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
