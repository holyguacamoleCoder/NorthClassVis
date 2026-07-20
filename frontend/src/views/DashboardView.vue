<template>
  <div class="dashboard-scrollport">
    <div class="dashboard-view">
    <div class="header">
      <NavHeader />
    </div>
    <div class="body">
      <div class="main">
        <div class="top">
          <div class="scatter-view" v-if="studentClusterInfo" ref="scatterViewRef">
            <ScatterView v-if="true" />
          </div>
          <div class="portrait-view" ref="portraitViewRef">
            <PortraitView />
          </div>
        </div>
        <div class="bottom">
          <div class="question-view" ref="questionViewRef">
            <QuestionView />
          </div>
          <div class="week-view" v-if="studentClusterInfo" ref="weekViewRef">
            <WeekView />
          </div>
        </div>
      </div>
      <div class="panel" ref="studentViewRef">
        <div class="student-view" v-if="studentClusterInfo">
          <StudentView />
        </div>
      </div>
    </div>
    </div>

    <AgentChatPanel
      layout="float"
      :visible="getAgentPanelVisible"
      :minimized="getAgentPanelMinimized"
      :context="agentContext"
      @close="closeAgentPanel"
      @minimize="minimizeAgentPanel"
      @expand="expandAgentPanel"
      @visual-link-click="onAgentVisualLinkClick"
    />
  </div>
</template>

<script>
import NavHeader from '@/components/NavHeader.vue'
import ScatterView from '@/components/ScatterView.vue'
import PortraitView from '@/components/PortraitView.vue'
import QuestionView from '@/components/QuestionView.vue'
import WeekView from '@/components/WeekView.vue'
import StudentView from '@/components/StudentView.vue'
import AgentChatPanel from '@/components/AgentChatPanel.vue'
import { mapActions, mapGetters } from 'vuex'

export default {
  name: 'DashboardView',
  components: {
    NavHeader,
    AgentChatPanel,
    ScatterView,
    PortraitView,
    QuestionView,
    WeekView,
    StudentView,
  },
  computed: {
    ...mapGetters([
      'getStudentClusterInfo',
      'getAgentPanelVisible',
      'getAgentPanelMinimized',
      'getAgentVisualLink',
      'getSelectedIds',
      'getNavSelectedClasses',
      'getNavSelectedMajors',
      'getNavWeekRange',
      'getAgentChatAttachments',
    ]),
    studentClusterInfo() {
      return this.getStudentClusterInfo
    },
    agentContext() {
      const extras = this.getAgentChatAttachments || {}
      return {
        classes: this.getNavSelectedClasses || [],
        majors: this.getNavSelectedMajors || [],
        week_range: this.getNavWeekRange || undefined,
        selected_student_ids: this.getSelectedIds || [],
        knowledge_ids: extras.knowledge_ids || [],
        title_ids: extras.title_ids || [],
        dataset: extras.dataset || null,
        view_snapshot: extras.view_snapshot || null,
        report: extras.report || null,
      }
    },
  },
  mounted() {
    this.fetchClusterData()
    this.$nextTick(() => {
      const link = this.getAgentVisualLink
      if (link?.view) {
        this.scrollToView(link.view)
      }
    })
  },
  methods: {
    ...mapActions([
      'fetchClusterData',
      'closeAgentPanel',
      'minimizeAgentPanel',
      'expandAgentPanel',
      'setAgentVisualLink',
    ]),
    viewToFriendlyName(view) {
      const map = {
        QuestionView: '题目视图',
        WeekView: '周趋势视图',
        StudentView: '学生列表',
        ScatterView: '散点视图',
        PortraitView: '画像视图',
      }
      return map[view] || view
    },
    buildJumpFeedbackText({ view, params }) {
      const name = this.viewToFriendlyName(view)
      let suffix = ''
      if (params && params.knowledge) suffix = `（${params.knowledge}）`
      else if (params && params.kind != null) suffix = `（簇 ${Number(params.kind) - 1}）`
      else if (params && params.cluster_id != null) suffix = `（cluster ${params.cluster_id}）`
      else if (params && Array.isArray(params.week_range) && params.week_range.length >= 2) {
        suffix = `（第 ${params.week_range[0]}–${params.week_range[1]} 周）`
      } else if (params && Array.isArray(params.student_ids) && params.student_ids.length) {
        suffix = '（建议关注学生）'
      }
      return `已跳转到${name}${suffix}`
    },
    async onAgentVisualLinkClick({ view, params }) {
      const merged = { ...(params || {}) }
      if (view === 'WeekView' && !merged.week_range && this.getNavWeekRange?.length >= 2) {
        merged.week_range = [...this.getNavWeekRange]
      }
      await this.$store.dispatch('applyAgentVisualLinkNavigation', { view, params: merged })
      const feedback = this.buildJumpFeedbackText({ view, params: merged })
      this.$store.commit('setAgentJumpFeedback', feedback)
      if (this._agentFeedbackTimer) clearTimeout(this._agentFeedbackTimer)
      this._agentFeedbackTimer = setTimeout(() => {
        this.$store.commit('setAgentJumpFeedback', '')
        this._agentFeedbackTimer = null
      }, 3000)
      await this.$nextTick()
      this.scrollToView(view)
    },
    scrollToView(view) {
      const refMap = {
        QuestionView: 'questionViewRef',
        WeekView: 'weekViewRef',
        StudentView: 'studentViewRef',
        ScatterView: 'scatterViewRef',
        PortraitView: 'portraitViewRef',
      }
      const refName = refMap[view]
      if (!refName || !this.$refs[refName]) return
      const el = this.$refs[refName].$el || this.$refs[refName]
      const port = this.$el
      if (!el || !port) return
      const portRect = port.getBoundingClientRect()
      const elRect = el.getBoundingClientRect()
      const pad = 8
      if (elRect.right > portRect.right - pad) {
        port.scrollLeft += elRect.right - portRect.right + pad
      } else if (elRect.left < portRect.left + pad) {
        port.scrollLeft += elRect.left - portRect.left - pad
      }
      if (view === 'StudentView' && elRect.top < portRect.top + pad) {
        port.scrollTop += elRect.top - portRect.top - pad
      }
    },
  },
}
</script>

<style scoped lang="less">
@spacing: 4px;
@total-width: 2300px + @spacing * 2;
@total-height: 1250px + @spacing * 3;
@panel-color: #fff;
@background-color: #ccc;
@border-radius: 5px;

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
  gap: @spacing;
}

.dashboard-scrollport {
  width: 100%;
  min-height: 100vh;
  overflow: auto;
  background-color: @background-color;
  display: flex;
  justify-content: center;
  align-items: flex-start;
}

.dashboard-view {
  width: @total-width;
  min-width: @total-width;
  height: @total-height;
  margin: @spacing 0;
  padding: 0 @spacing;
  display: flex;
  flex-direction: column;
  align-items: center;
  border-radius: 5px;
  flex-shrink: 0;
  box-sizing: border-box;
}

@header-height: 50px;
.header {
  width: @total-width;
  height: @header-height;
  flex-shrink: 0;
}

.body {
  width: @total-width;
  display: flex;
  flex-shrink: 0;
}

@main-width: 1850px;
.main {
  width: @main-width;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;

  .top,
  .bottom {
    width: inherit;
    height: 600px;
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    gap: @spacing;
    flex-shrink: 0;
  }
}

.view() {
  background-color: @panel-color;
  border-radius: @border-radius;
  border: 1px solid #a8a8a8;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12);
  box-sizing: border-box;
}

.scatter-view {
  .view();
  width: 400px;
  height: 600px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-sizing: border-box;

  :deep(#scatter-chart) {
    flex: 1;
    min-height: 0;
    width: 100%;
  }
}
.portrait-view {
  .view();
  width: 1450px;
  height: 600px;
  flex-shrink: 0;
}
.question-view {
  .view();
  width: 675px;
  height: 600px;
  flex-shrink: 0;
}
.week-view {
  .view();
  width: 1175px;
  height: 600px;
  flex-shrink: 0;
}

@panel-height: @total-height - @header-height - @spacing * 2;
.panel {
  .view();
  width: 450px;
  height: @panel-height;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  .student-view {
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }
}
</style>
