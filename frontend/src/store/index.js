import { createStore } from 'vuex'
import { getClusterEveryone } from '@/api/ParallelView.js'

export default createStore({
  state: {
    clusterData: null,
    justClusterData: null,
    selectedStudentIds: [],
    selectedStudentData: [],
    colors: ['#ff7f00', '#377eb8', '#4daf4a'],
    hadFilter: false
  },
  mutations: {
    setClusterData(state, data) {
      state.clusterData = data
    },
    setJustClusterData(state, data) {
      state.justClusterData = data
    },
    setSelectedStudents(state, student_id){
      const index = state.selectedStudentIds.indexOf(student_id)
      if(index === -1){
        state.selectedStudentIds.push(student_id)
      }else{
        state.selectedStudentIds.splice(index, 1)
      }
    },
    setStudentData(state){
      state.selectedStudentIds.forEach(item =>{
        state.selectedStudentData.push(state.clusterData[item])
      })
    },
    setHadFilter(state){
      state.hadFilter = !state.hadFilter
    }
  },
  actions: {
    async fetchClusterData(context) {
      const startTime = performance.now(); // 记录开始时间
      const { data } = await getClusterEveryone()
      // console.log('data', data)
      const RData = {}
      for (let key in data){
        RData[key] = data[key].cluster
      }
      context.commit('setClusterData', data)
      context.commit('setJustClusterData', RData)
      // console.log('clusterData', this.state.clusterData)
      // console.log('justClusterData', this.state.justClusterData)
      const endTime = performance.now(); // 记录结束时间
      console.log(`Trans time: ${endTime - startTime} milliseconds`)
    },
    toggleSelection(context, student_id){
      context.commit('setSelectedStudents', student_id)
      context.commit('setStudentData')
      // console.log('selectStudentData', this.state.selectedStudentData)
    },
    toggleHadFilter(context){
      context.commit('setHadFilter')
    }
  },
  getters: {
    getClusterData(state) {
      return state.clusterData
    },
    getJustClusterData(state) {
      return state.justClusterData
    },
    getSelection(state){
      return state.selectedStudentIds
    },
    getSelectionData(state){
      return state.selectedStudentData
    },
    getColors(state){
      return state.colors
    },
    getHadFilter(state){
      return state.hadFilter
    }
  }
})