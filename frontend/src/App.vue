<template>
<div class="app-container">
  <div class="header">
    <NavHeader/>
  </div>  
  <div class="body">
    <div class="main">
      <div class="top">
        <!-- A. Scatter View or Parallel View -->
        <div class="scatter-view" v-if="studentClusterInfo">
          <ParallelView v-if="false"/>
          <ScatterView/>
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
        
        <!-- D. Week View -->
        <div class="week-view" v-if="studentClusterInfo">
          <WeekView />
        </div>
      </div>
    </div>

    <!-- E. Student View -->
    <div class="panel">
       <div class="student-view" v-if="studentClusterInfo">
         <StudentView />
       </div>
    </div>
  </div>

</div> 
</template>

<script>
import NavHeader from './components/NavHeader.vue'
import ParallelView from './components/ParallelView.vue'
import ScatterView from './components/ScatterView.vue'
import PortraitView from './components/PortraitView.vue'
import QuestionView from './components/QuestionView.vue'
import WeekView from './components/WeekView.vue'
import StudentView from './components/StudentView.vue'
import { mapActions, mapGetters } from 'vuex'
export default {
  components: {
    NavHeader,
    ParallelView,
    ScatterView,
    PortraitView,
    QuestionView,
    WeekView,
    StudentView,
  },
  data() {
    return {
      
    }
  },
  computed: {
    ...mapGetters(['getStudentClusterInfo']),
    studentClusterInfo(){
      return this.getStudentClusterInfo
    }
  },
  async created() {
   
  },
  mounted() {
    this.fetchClusterData()
    
  },
  methods: {
    ...mapActions(['fetchClusterData']),
  },
  watch: {
    
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
