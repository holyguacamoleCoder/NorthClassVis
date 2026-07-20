<template>
  <div class="agent-msg-bubble agent-msg-bubble--assistant agent-msg-bubble--enter">
    <div
      v-if="msg.streaming && msg.statusHint && !hasAnyContent(msg)"
      class="agent-stream-hint"
    >
      {{ msg.statusHint }}
    </div>

    <!-- ① 步骤组：思路 / 步骤 N + 对应工具（真计划见侧栏 todo） -->
    <AgentStepGroup
      v-for="(group, idx) in visibleStepGroups(msg)"
      :key="group.id"
      :group="group"
      :streaming="!!msg.streaming"
      :stream-narration="streamNarrationForGroup(msg, group, idx)"
      :running-tool="stepGroupRunningTool(msg, idx)"
      :default-expanded="stepGroupExpanded(msg, group, idx)"
      :run-actions-enabled="!loading || !!msg.streaming"
      :primary-modify-run-id="primaryModifyRunId(msg)"
      :show-modify-button="showModifyForGroup(msg, group, idx)"
      class="agent-reveal"
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
    <div
      v-if="showReportDeliveryBlock(msg)"
      class="agent-report-validate-block agent-reveal"
      :class="reportDeliveryBlockClass(msg)"
    >
      <div class="agent-section-label">{{ reportDeliverySectionLabel(msg) }}</div>
      <p class="agent-report-validate-text">{{ reportDeliveryText(msg) }}</p>
      <ul v-if="reportDeliveryIssues(msg).length" class="agent-report-validate-errors">
        <li v-for="(err, i) in reportDeliveryIssues(msg)" :key="i">{{ err }}</li>
      </ul>
    </div>
    <AgentReportEvidence
      v-if="showReportEvidence(msg)"
      class="agent-reveal"
      :items="msg.report_evidence"
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
import AgentStepGroup from '@/components/agent/AgentStepGroup.vue'
import AgentDeliverableLinks from '@/components/agent/AgentDeliverableLinks.vue'
import AgentReportEvidence from '@/components/agent/AgentReportEvidence.vue'
import AgentMemorySaved from '@/components/agent/AgentMemorySaved.vue'
import { AGENT_UI } from '@/constants/agentUiText.js'
import {
  buildStepGroupsFromMessage,
  pickPrimaryModifyRun,
  stepGroupDefaultExpanded,
} from '@/utils/agentTimeline.js'
import { stripVisualLinkMarkdown, findVisualLinkFromMarkdownClick } from '@/utils/visualLinks.js'
import { stripReportLinkMarkdown, findReportLinkFromMarkdownClick } from '@/utils/reportLinks.js'

export default {
  name: 'AgentAssistantMessage',
  components: {
    AgentMarkdown,
    AgentStreamingMarkdown,
    AgentStepGroup,
    AgentDeliverableLinks,
    AgentReportEvidence,
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
    stepGroups(msg) {
      return buildStepGroupsFromMessage(msg)
    },
    visibleStepGroups(msg) {
      let groups = this.stepGroups(msg)
      if (
        !groups.length &&
        msg.streaming &&
        ((msg.thinking && msg.thinking.trim()) || this.runningTool)
      ) {
        groups = [{
          id: 'plan',
          phase: 'plan',
          text: String(msg.thinking || '').trim(),
          tools: [],
        }]
      }
      if (msg.streaming) return groups
      if (this.revealPhase(msg) >= 1) return groups
      return []
    },
    stepGroupExpanded(msg, group, idx) {
      return stepGroupDefaultExpanded(group, idx, this.stepGroups(msg), msg)
    },
    streamNarrationForGroup(msg, group, idx) {
      if (!msg.streaming) return false
      const groups = this.visibleStepGroups(msg)
      if (group.phase === 'plan') {
        return !this.hasThinkingUpdates(msg)
      }
      if (group.phase === 'plan_update') {
        return idx === groups.length - 1
      }
      return false
    },
    stepGroupRunningTool(msg, idx) {
      if (!msg.streaming || !this.runningTool) return null
      const groups = this.visibleStepGroups(msg)
      if (idx !== groups.length - 1) return null
      return this.runningTool
    },
    allToolSteps(msg) {
      const steps = []
      for (const group of this.stepGroups(msg)) {
        for (const item of group.tools || []) {
          if (item.kind === 'tool' && item.step) steps.push(item.step)
        }
      }
      if (msg.streaming && this.runningTool) {
        steps.push({ tool: this.runningTool.tool, run_id: this.runningTool.run_id, status: 'running' })
      }
      return steps
    },
    primaryModifyRunId(msg) {
      return pickPrimaryModifyRun(this.allToolSteps(msg))?.run_id || ''
    },
    showModifyForGroup(msg, group, idx) {
      const primary = pickPrimaryModifyRun(this.allToolSteps(msg))
      if (!primary) return false
      const groupSteps = (group.tools || [])
        .filter((item) => item.kind === 'tool' && item.step)
        .map((item) => item.step)
      const inGroup = groupSteps.some((s) => s.run_id && s.run_id === primary.run_id)
      if (!inGroup) return false
      const groups = this.stepGroups(msg)
      for (let i = groups.length - 1; i >= 0; i -= 1) {
        const gSteps = (groups[i].tools || [])
          .filter((item) => item.kind === 'tool' && item.step)
          .map((item) => item.step)
        if (gSteps.some((s) => s.run_id && s.run_id === primary.run_id)) {
          return i === idx
        }
      }
      return false
    },
    hasAnyContent(msg) {
      return (
        this.stepGroups(msg).some((g) => g.text.trim() || (g.tools && g.tools.length)) ||
        (msg.answer && msg.answer.trim()) ||
        (msg.closing && msg.closing.trim()) ||
        (msg.streaming && this.runningTool)
      )
    },
    thinkingUpdates(msg) {
      if (Array.isArray(msg.thinking_updates) && msg.thinking_updates.length) {
        return msg.thinking_updates.filter((t) => String(t || '').trim())
      }
      const tl = msg.timeline || []
      return tl
        .filter((item) => item.kind === 'narration' && item.phase === 'plan_update')
        .map((item) => String(item.text || '').trim())
        .filter(Boolean)
    },
    hasThinkingUpdates(msg) {
      return this.thinkingUpdates(msg).length > 0
    },
    isLastThinkingUpdate(msg, idx) {
      const list = this.thinkingUpdates(msg)
      return idx === list.length - 1
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
    showReportEvidence(msg) {
      if (msg.streaming) return false
      const items = msg.report_evidence || []
      if (!items.length) return false
      return this.revealPhase(msg) >= 2
    },
    showReportDeliveryBlock(msg) {
      if (msg.streaming) return false
      const check = msg.report_final_check
      if (!check) return false
      const links = msg.report_links || []
      if (!links.length) return false
      return this.revealPhase(msg) >= 2
    },
    reportDeliveryStatus(msg) {
      const check = msg.report_final_check || {}
      if (check.delivery_status) return check.delivery_status
      if (check.ok === false) return 'fail'
      const warnings = Array.isArray(check.warnings) ? check.warnings : []
      return warnings.length ? 'warn' : 'pass'
    },
    reportDeliveryBlockClass(msg) {
      const status = this.reportDeliveryStatus(msg)
      if (status === 'pass') return 'agent-report-delivery-pass'
      if (status === 'warn') return 'agent-report-delivery-warn'
      return 'agent-report-delivery-fail'
    },
    reportDeliverySectionLabel(msg) {
      const status = this.reportDeliveryStatus(msg)
      if (status === 'pass') return this.ui.reportValidatePassSection
      if (status === 'warn') return this.ui.reportValidateWarnSection
      return this.ui.reportValidateSection
    },
    reportDeliveryText(msg) {
      const check = msg.report_final_check || {}
      const fixes = Array.isArray(check.fixes) ? check.fixes : []
      const fixed = fixes.length ? `已自动修复：${fixes.join('；')}。` : ''
      const status = this.reportDeliveryStatus(msg)
      if (status === 'pass') return `${fixed}${this.ui.reportValidatePassHint}`
      if (status === 'warn') return `${fixed}${this.ui.reportValidateWarnHint}`
      return `${fixed}${this.ui.reportValidateFailHint}`
    },
    reportDeliveryIssues(msg) {
      const check = msg.report_final_check || {}
      const status = this.reportDeliveryStatus(msg)
      if (status === 'fail') {
        return Array.isArray(check.errors) ? check.errors.slice(0, 3) : []
      }
      if (status === 'warn') {
        return Array.isArray(check.warnings) ? check.warnings.slice(0, 3) : []
      }
      return []
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
.agent-plan-block--update {
  background: rgba(55, 126, 184, 0.04);
  border-left-color: #5a9fd4;
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
.agent-report-validate-block {
  margin-top: 10px;
  padding: 8px 10px;
  border-radius: 4px;
  border-left: 3px solid #c62828;
  background: #fff5f5;
}
.agent-report-delivery-pass {
  border-left-color: #2e7d32;
  background: #f1f8f4;
}
.agent-report-delivery-warn {
  border-left-color: #f9a825;
  background: #fffbf0;
}
.agent-report-delivery-fail {
  border-left-color: #c62828;
  background: #fff5f5;
}
.agent-report-validate-text {
  margin: 4px 0 6px;
  font-size: 13px;
  color: #555;
  line-height: 1.45;
}
.agent-report-validate-errors {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
}
.agent-report-delivery-pass .agent-report-validate-errors { color: #2e7d32; }
.agent-report-delivery-warn .agent-report-validate-errors { color: #856404; }
.agent-report-delivery-fail .agent-report-validate-errors { color: #c62828; }
.agent-reveal { animation: agent-fade-in 0.35s ease-out forwards; }
.agent-stagger { animation: agent-fade-in 0.3s ease-out backwards; }
@keyframes agent-fade-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
