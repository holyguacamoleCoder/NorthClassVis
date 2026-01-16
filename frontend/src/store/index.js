import { createStore } from 'vuex'
import { getClusterEveryone } from '@/api/ParallelView.js'
import { getSelectedData } from '@/api/NavHeader.js'


export default createStore({
  state: {
    configLoaded: 0,    // 表示后端配置是否加载完成
    studentClusterInfo: {}, // 存储从后端获取的聚类数据,key:stu_id,value:cluster
    selectedStudentIds: [], // 存储选中的学生 ID ，从前端交互而来
    selectedStudentData: [], // 对应的学生各项指标数据，需要从后端获取
    colors: ['#ff7f00', '#377eb8', '#4daf4a'],
  },
  mutations: {
    // 更新 configLoaded 状态
    SET_CONFIG_LOADED(state, value) {
      state.configLoaded = value;
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
  },
  actions: {
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
  },
  getters: {
    getConfigLoaded: state => state.configLoaded,
    getStudentClusterInfo: state => state.studentClusterInfo,
    getSelectedIds: state => state.selectedStudentIds,
    getSelectedData: state => state.selectedStudentData,
    getColors: state => state.colors,
  }
})