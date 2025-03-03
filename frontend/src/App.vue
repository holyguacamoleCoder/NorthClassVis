<template>
<div class="app-container">
  <div class="header"><HeaderConfig /></div>  
  <div class="body">
    <div class="main">
      <div class="top">
        <!-- A. Scatter View -->
        <div class="scatter-view" v-if="clusterData">
          <ParallelView v-if="false"/>
          <ScatterView />
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
import ScatterView from './components/ScatterView.vue'
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
    ScatterView,
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
@spacing: 4px;
@total-width : 2300px + @spacing * 2;
@total-height : 1250px + @spacing * 3;
@panel-color: #fff;
@background-color: #ccc;
@border-radius: 5px;
*{
  margin: 0;
  padding: 0;
  box-sizing: border-box;
  gap: @spacing;
}
.app-container {
  width: @total-width;
  height: @total-height;
  background-color: @background-color;
  padding: 0 @spacing;
  display: flex;
  flex-direction: column;
  align-items: center;
  border-radius: 5px;
}

@header-height: 50px;
.header{
  width: @total-width;
  height: @header-height;
}

.body {
  width: @total-width;
  display: flex;
}

@main-width: 1850px;
.main{
  width: @main-width;
  display: flex;
  flex-direction: column;
  
  .top
  ,.bottom{
    width: inherit;
    height: 600px;
    display: flex;
    flex-direction: row;
    justify-content: space-between;
  }
  
}

.view(){
  background-color: @panel-color;
  border-radius: @border-radius;
}
.scatter-view{
  .view();
  width: 400px;
  height: 600px;
}
.portrait-view{
  .view();
  width: 1450px;
  height: 600px;
}
.question-view{
  .view();
  width: 675px;
  height: 600px;
}
.week-view{
  .view();
  width: 1175px;
  height: 600px;
}
@panel-height: @total-height - @header-height - @spacing * 2;
.panel{
  .view();
  width: 450px;
  height: @panel-height;
}

</style>
