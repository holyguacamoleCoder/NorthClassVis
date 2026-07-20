import { createStore } from 'vuex'
import { getClusterEveryone } from '@/api/ParallelView.js'
import { getSelectedData } from '@/api/NavHeader.js'
import { setConfig } from '@/api/ConfigPanel.js'

export function coerceWeekRange(value) {
  if (value == null) return null
  if (Array.isArray(value) && value.length >= 2) {
    const start = Number(value[0])
    const end = Number(value[1])
    if (!Number.isNaN(start) && !Number.isNaN(end)) return [start, end]
  }
  return null
}

/** 链接 params → store → 已有 navWeekRange */
function resolveWeekRangeForNavigation(state, params = {}) {
  return coerceWeekRange(params.week_range) || coerceWeekRange(state.navWeekRange)
}

/** WeekView 空 params 表示「当前选中学生的全部簇」；无选中时用 nav 聚类全集 */
function resolveVisualLinkStudentIds(state, view, params = {}) {
  const fromParams = Array.isArray(params.student_ids)
    ? params.student_ids.map(String).filter(Boolean)
    : []
  if (fromParams.length) return fromParams

  const selected = state.selectedStudentIds || []
  if (selected.length) return [...selected]

  const suggested = state.agentSuggestedStudentIds || []
  if (suggested.length) return [...suggested]

  if (view === 'WeekView') {
    const cluster = state.studentClusterInfo || {}
    return Object.keys(cluster).filter(Boolean)
  }
  return []
}

export default createStore({
  state: {
    configLoaded: 0,    // 表示后端配置是否加载完成
    navConfigRevision: 0, // 每次应用 nav 筛选 +1，供散点等视图可靠刷新
    studentClusterInfo: {}, // 存储从后端获取的聚类数据,key:stu_id,value:cluster
    selectedStudentIds: [], // 存储选中的学生 ID ，从前端交互而来
    selectedStudentData: [], // 对应的学生各项指标数据，需要从后端获取
    colors: ['#ff7f00', '#377eb8', '#4daf4a'],
    // Agent 浮层
    agentPanelVisible: false,
    agentPanelMinimized: false,
    agentVisualLink: null, // { view, params } 图表联动占位
    agentHighlightAt: 0, // 最近一次跳转时间戳，用于目标视图高亮
    agentJumpFeedback: '', // 跳转后给聊天浮窗展示的文案，若干秒后清除
    agentSuggestedStudentIds: [], // 仅当用户点击「应用到选择」时才写入 selectedStudentIds，避免牵一发而动全身
    navClasses: '未选',
    navMajors: '未选',
    navSelectedClasses: [],
    navSelectedMajors: [],
    navWeekRange: null,
    navScopeApplying: false,
    /** Manual composer attachments (knowledge / dataset / view / report). */
    agentChatAttachments: {
      knowledge_ids: [],
      title_ids: [],
      dataset: null,
      view_snapshot: null,
      report: null,
    },
  },
  mutations: {
    // 更新 configLoaded 状态
    SET_CONFIG_LOADED(state, value) {
      state.configLoaded = value;
    },
    NAV_CONFIG_APPLIED(state) {
      state.navConfigRevision += 1
      state.configLoaded = Date.now()
    },
    setNavScopeApplying(state, value) {
      state.navScopeApplying = !!value
    },

    // 设置 studentClusterInfo
    setStudentClusterInfo(state, data) {
      state.studentClusterInfo = data
    },

    // 切换学生 ID 的选中状态（添加或移除）
    setSelectedStudents(state, student_ids){
      state.selectedStudentIds = student_ids
    },

    // 设置selectedStudentData
    setSelectedStudentData(state, students_data){
      state.selectedStudentData = students_data
    },
    setAgentPanelVisible(state, visible) {
      state.agentPanelVisible = visible
    },
    setAgentPanelMinimized(state, minimized) {
      state.agentPanelMinimized = minimized
    },
    setAgentVisualLink(state, payload) {
      state.agentVisualLink = payload
    },
    setAgentHighlightAt(state, timestamp) {
      state.agentHighlightAt = timestamp || 0
    },
    setAgentJumpFeedback(state, message) {
      state.agentJumpFeedback = message || ''
    },
    setAgentSuggestedStudentIds(state, ids) {
      state.agentSuggestedStudentIds = Array.isArray(ids) ? ids : []
    },
    setNavFilter(state, { classes, majors }) {
      if (classes != null) state.navClasses = classes
      if (majors != null) state.navMajors = majors
    },
    setNavScope(state, payload) {
      if (!payload) return
      if (payload.classes != null) state.navSelectedClasses = payload.classes
      if (payload.majors != null) state.navSelectedMajors = payload.majors
      if (payload.weekRange !== undefined) state.navWeekRange = payload.weekRange
      if (payload.classesLabel != null) state.navClasses = payload.classesLabel
      if (payload.majorsLabel != null) state.navMajors = payload.majorsLabel
    },
    patchAgentChatAttachments(state, patch) {
      if (!patch || typeof patch !== 'object') return
      const next = { ...state.agentChatAttachments }
      if ('knowledge_ids' in patch) {
        next.knowledge_ids = Array.isArray(patch.knowledge_ids)
          ? patch.knowledge_ids.map(String).filter(Boolean)
          : []
      }
      if ('title_ids' in patch) {
        next.title_ids = Array.isArray(patch.title_ids)
          ? patch.title_ids.map(String).filter(Boolean)
          : []
      }
      if ('dataset' in patch) next.dataset = patch.dataset || null
      if ('view_snapshot' in patch) next.view_snapshot = patch.view_snapshot || null
      if ('report' in patch) next.report = patch.report || null
      state.agentChatAttachments = next
    },
    clearAgentChatAttachments(state) {
      state.agentChatAttachments = {
        knowledge_ids: [],
        title_ids: [],
        dataset: null,
        view_snapshot: null,
        report: null,
      }
    },
  },
  actions: {
    attachQuestionScopeToChat(context, { knowledge_ids, title_ids } = {}) {
      context.commit('patchAgentChatAttachments', {
        knowledge_ids: knowledge_ids || [],
        title_ids: title_ids || [],
      })
      context.commit('setAgentPanelVisible', true)
      context.commit('setAgentPanelMinimized', false)
    },
    attachDatasetToChat(context, dataset) {
      if (!dataset) return
      context.commit('patchAgentChatAttachments', { dataset })
      context.commit('setAgentPanelVisible', true)
      context.commit('setAgentPanelMinimized', false)
    },
    attachViewSnapshotToChat(context, snapshot) {
      if (!snapshot?.view) return
      context.commit('patchAgentChatAttachments', { view_snapshot: snapshot })
      context.commit('setAgentPanelVisible', true)
      context.commit('setAgentPanelMinimized', false)
    },
    attachReportToChat(context, report) {
      if (!report?.path) return
      context.commit('patchAgentChatAttachments', { report })
      context.commit('setAgentPanelVisible', true)
      context.commit('setAgentPanelMinimized', false)
    },
    clearComposerChatAttachments(context) {
      context.commit('clearAgentChatAttachments')
    },
    // 后端获取数据:{stu_id: cluster}
    async fetchClusterData(context) {
      const { data } = await getClusterEveryone()
      context.commit('setStudentClusterInfo', data)
    },
    // 前端交互获得被选中的学生id
    toggleSelectedIds(context, student_ids){
      context.commit('setSelectedStudents', student_ids)
      // console.log('selectedStudentIds', student_ids)
    },
    // 后端获取被选中的学生数据
    /**
     * 返回的数据格式：
     * stu_id:{
     *  "bonus": {xxx},
     *  "knowledge": {xxx}
     * } 
     */
    async fetchSelectedData(context){
      // 检查是否有选中的学生
      if (!context.state.selectedStudentIds || context.state.selectedStudentIds.length === 0) {
        console.warn('No students selected')
        return
      }
      
      try {
        const { data } = await getSelectedData(context.state.selectedStudentIds)
        const selectedStudentData = {}
        
        // 确保 data 存在且是对象
        if (!data) {
          console.error('No data received from server')
          return
        }
        
        for(let i = 0; i < context.state.selectedStudentIds.length; i++){
          const studentId = context.state.selectedStudentIds[i]
          // 检查后端返回的数据中是否包含该学生
          if (data[studentId]) {
            selectedStudentData[studentId] = {
              ...data[studentId],
              cluster: context.state.studentClusterInfo[studentId]
            }
          } else {
            console.warn(`Student ${studentId} not found in server response`)
          }
        }
        context.commit('setSelectedStudentData', selectedStudentData)
      } catch (error) {
        console.error('Error fetching selected data:', error)
        alert('Failed to fetch selected student data. Please try again.')
      }
    },
    openAgentPanel(context) {
      context.commit('setAgentPanelVisible', true)
      context.commit('setAgentPanelMinimized', false)
    },
    closeAgentPanel(context) {
      context.commit('setAgentPanelVisible', false)
      context.commit('setAgentPanelMinimized', false)
    },
    minimizeAgentPanel(context) {
      context.commit('setAgentPanelMinimized', true)
    },
    expandAgentPanel(context) {
      context.commit('setAgentPanelMinimized', false)
    },
    setAgentVisualLink(context, payload) {
      context.commit('setAgentVisualLink', payload)
      context.commit('setAgentHighlightAt', Date.now())
    },
    /** 会话 filter_context → Nav 右栏 / 面板周次（classes、majors、week_range） */
    syncNavScopeFromFilterContext(context, filterContext) {
      if (!filterContext || typeof filterContext !== 'object') return
      const payload = {}
      if (Array.isArray(filterContext.classes) && filterContext.classes.length) {
        payload.classes = filterContext.classes
      }
      if (Array.isArray(filterContext.majors) && filterContext.majors.length) {
        payload.majors = filterContext.majors
      }
      const wr = coerceWeekRange(filterContext.week_range)
      if (wr) payload.weekRange = wr
      if (Object.keys(payload).length) {
        context.commit('setNavScope', payload)
      }
    },
    /** 图表入口点击：写入链接、同步选中学生并拉取详情 */
    async applyAgentVisualLinkNavigation(context, { view, params = {} }) {
      const weekRange = resolveWeekRangeForNavigation(context.state, params)
      const linkParams = { ...params }
      if (weekRange) linkParams.week_range = weekRange

      context.commit('setAgentVisualLink', { view, params: linkParams })
      context.commit('setAgentHighlightAt', Date.now())

      if (view === 'WeekView') {
        if (weekRange) {
          context.commit('setNavScope', { weekRange })
        }
        const clusterKeys = Object.keys(context.state.studentClusterInfo || {})
        if (!clusterKeys.length) {
          await context.dispatch('fetchClusterData')
        }
      }

      const ids = resolveVisualLinkStudentIds(context.state, view, linkParams)
      if (ids.length > 0) {
        context.commit('setAgentSuggestedStudentIds', ids)
        context.commit('setSelectedStudents', ids)
        if (view === 'WeekView' || view === 'StudentView') {
          await context.dispatch('fetchSelectedData')
        }
      }

      if (view === 'WeekView') {
        await context.dispatch('pushNavScopeToServer')
      }
    },
    applyAgentSuggestedStudents(context) {
      const ids = context.state.agentSuggestedStudentIds
      if (!ids || ids.length === 0) return
      context.commit('setSelectedStudents', ids)
      return context.dispatch('fetchSelectedData')
    },
    applyNavConfig(context) {
      context.commit('NAV_CONFIG_APPLIED')
    },
    async pushNavScopeToServer(context) {
      const classes = context.state.navSelectedClasses || []
      const majors = context.state.navSelectedMajors || []
      const weekRange = context.state.navWeekRange
      if (!classes.length || !majors.length) return
      try {
        await setConfig(classes, majors, weekRange)
        context.commit('NAV_CONFIG_APPLIED')
      } catch (err) {
        console.error('pushNavScopeToServer failed', err)
      }
    },
    async syncDashboardFromAgentScope(context) {
      await context.dispatch('fetchClusterData')
      await context.dispatch('pushNavScopeToServer')
      const ids = context.state.selectedStudentIds
      if (ids && ids.length > 0) {
        await context.dispatch('fetchSelectedData')
      }
    },
  },
  getters: {
    getConfigLoaded: state => state.configLoaded,
    getNavConfigRevision: state => state.navConfigRevision,
    getStudentClusterInfo: state => state.studentClusterInfo,
    getSelectedIds: state => state.selectedStudentIds,
    getSelectedData: state => state.selectedStudentData,
    getColors: state => state.colors,
    getAgentPanelVisible: state => state.agentPanelVisible,
    getAgentPanelMinimized: state => state.agentPanelMinimized,
    getAgentVisualLink: state => state.agentVisualLink,
    getAgentHighlightAt: state => state.agentHighlightAt,
    getAgentJumpFeedback: state => state.agentJumpFeedback,
    getAgentSuggestedStudentIds: state => state.agentSuggestedStudentIds,
    getNavClasses: state => state.navClasses,
    getNavMajors: state => state.navMajors,
    getNavSelectedClasses: state => state.navSelectedClasses,
    getNavSelectedMajors: state => state.navSelectedMajors,
    getNavWeekRange: state => state.navWeekRange,
    getNavScopeApplying: state => state.navScopeApplying,
    getAgentChatAttachments: state => state.agentChatAttachments,
  }
})