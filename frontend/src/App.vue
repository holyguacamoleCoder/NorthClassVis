<template>
<div class="app-container">
  <div class="header"><HeaderConfig /></div>  
  <div class="body">
    <div class="main">
      <div class="top">
        <!-- A. Scatter View -->
        <div class="scatter-view" v-if="clusterData">
          <ParallelView />
        </div>
        
        <!-- B. Portrait View -->
        <div class="portrait-view" >
          <PortraitView />
        </div>
      </div>
      
      <div class="bottom">
        <!-- C. Question View -->
        <div class="question-view">
          <QuestionView />
        </div>
        
        <!-- D. Question Tooltip -->
        <div class="week-view" v-if="JustClusterData">
          <WeekView />
        </div>
      </div>
    </div>

    <!-- E. Student View -->
    <div class="panel">
       <div class="student-view" v-if="JustClusterData">
         <StudentView />
       </div>
    </div>
  </div>
</div> 
</template>

<script>
import HeaderConfig from './components/HeaderConfig.vue'
import ParallelView from './components/ParallelView.vue'
import PortraitView from './components/PortraitView.vue'
import QuestionView from './components/QuestionView.vue'
import WeekView from './components/WeekView.vue'
import StudentView from './components/StudentView.vue'
import { mapActions, mapGetters } from 'vuex'
import { filterClasses, getFilter } from './api/App'
export default {
  components: {
    HeaderConfig,
    ParallelView,
    PortraitView,
    QuestionView,
    WeekView,
    StudentView,
  },
  data() {
    return {
      selectedClasses: 2,
      CheckoutAllClass: true,
      CheckoutClasses: []
    }
  },
  computed: {
    ...mapGetters(['getClusterData', 'getJustClusterData', 'getHadFilter']),
    clusterData(){
      return this.$store.state.clusterData
    },
    JustClusterData(){
      return this.$store.state.justClusterData
    },
    displayButton(){
      if(this.CheckoutAllClass) return 'All'
      if(this.CheckoutClasses.some(item => item.checked)) return 'Part'
      else return 'none'
    }
  },
  async created() {
    // for(let i = 1; i <= 15; i++){
    //   this.CheckoutClasses.push({checked: false, text: `Class${i}`, id: i})
    // }
    // this.CheckoutClasses[0].checked = true
    const {data} = await getFilter()
    this.CheckoutClasses =  data
    this.CheckoutAllClass = false
  },
  mounted() {
    this.fetchClusterData()
  },
  methods: {
    ...mapActions(['fetchClusterData', 'toggleHadFilter']),
    handleCheck(e){
      console.log(e.target.name)
      this.CheckoutClasses.checked = !this.CheckoutClasses.checked
      this.CheckoutAllClass = this.CheckoutClasses.every(item => item.checked)
      // console.log('change!!!')
    },
    handleAllCheck(){
      if(this.CheckoutClasses.every(item => item.checked) || this.CheckoutClasses.every(item => !item.checked))
        this.CheckoutClasses.forEach(item => item.checked = !item.checked)
      else{
        this.CheckoutClasses.forEach(item => item.checked = this.CheckoutAllClass)
      }
      // console.log('change!!!')
    },
    async submitClasses(e){
      e.preventDefault()
      const response = await filterClasses(this.CheckoutClasses)
      // console.log(response.data.data)
      this.CheckoutClasses = response.data.data
      this.toggleHadFilter()
    }
  },
  watch: {
    //监视被选中的学生实例
    getHadFilter(){
      // console.log('had filter change!!')
    }
  }
};
</script>

<style scoped lang="less">
*{
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}
@total_width : 2300px;
.app-container {
  width: @total_width;
  background-color: #ccc;
  border-radius: 5px;
.body {
  width: @total_width;
  height: 1230px;
  display: flex;
  .main{
    width: 1850px;
    height: inherit;
    display: flex;
    flex-direction: column;
    .top{
      width: inherit;
      height: 600px;
      display: flex;
      .scatter-view{
        width: 400px;
        height: 600px;
        height: inherit;
      }
      .portrait-view{
        width: 1450px;
        height: 600px;
      }
    }
    .bottom{
      width: inherit;
      height: 620px;
      display: flex;
      .question-view{
        width: 675px;
        height: 600px;
      }
      .week-view{
        margin-left: 5px;
        width: 1165px;
        height: 600px;
      }
    }
  }
  .panel{
    width: 450px;
    height: inherit;
  }
}

} //app-container
</style>
