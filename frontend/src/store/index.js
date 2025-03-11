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
      const { data } = await getSelectedData(context.state.selectedStudentIds)
      const selectedStudentData = {}
      for(let i = 0; i < context.state.selectedStudentIds.length; i++){
        selectedStudentData[context.state.selectedStudentIds[i]] = {
          ...data[context.state.selectedStudentIds[i]],
          cluster: context.state.studentClusterInfo[context.state.selectedStudentIds[i]]
        }
      }
      context.commit('setSelectedStudentData', selectedStudentData)
      // alert('已获取被选择数据')
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