<template>
  <AgentPageLayout :context="agentContext" @visual-link-click="onVisualLinkClick" />
</template>

<script>
import AgentPageLayout from '@/components/agent/AgentPageLayout.vue'
import { mapActions, mapGetters } from 'vuex'

export default {
  name: 'AgentView',
  components: { AgentPageLayout },
  mounted() {
    this.fetchClusterData()
  },
  computed: {
    ...mapGetters([
      'getSelectedIds',
      'getNavSelectedClasses',
      'getNavSelectedMajors',
      'getNavWeekRange',
      'getAgentChatAttachments',
    ]),
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
  methods: {
    ...mapActions(['fetchClusterData', 'syncDashboardFromAgentScope', 'applyAgentVisualLinkNavigation']),
    async onVisualLinkClick({ view, params }) {
      const merged = { ...(params || {}) }
      if (view === 'WeekView' && !merged.week_range && this.getNavWeekRange?.length >= 2) {
        merged.week_range = [...this.getNavWeekRange]
      }
      await this.syncDashboardFromAgentScope()
      await this.$router.push('/')
      await this.$nextTick()
      await this.applyAgentVisualLinkNavigation({ view, params: merged })
    },
  },
}
</script>
