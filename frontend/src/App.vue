<template>
  <div class="app-container">
  <div class="header">
    <div class="title">
      XD-stClusterVis
    </div>
    <div class="filter">
      <span>Class:  </span>
      <Dropdown>
        <!-- trigger element -->
        <template #trigger>
          <button type="button" style="font-weight: bold">
            {{displayButton}}
          </button>
        </template>
        <!-- contents display in dropdown -->
          <form id="checkboxs" name="myForm">
           <div class="" v-for="(item,index) in CheckoutClasses" :key="index"  
              style="border-radius: 5px; padding: 5px; width:180px;">
             <input 
             type="checkbox"
             checked
             style="width: 20px; height: 20px;"
             :name="item.text"
             v-model="item.checked"
             @change="handleCheck">
             <label
             style="list-style: none;
             border-bottom: 1px solid #ccc;
             margin-top: 5px;
             display: inline-block;
             width: 150px;
             padding-bottom: 8px;
             font-size: 25px;
             text-align: center;"
             >{{ item.text }}</label>
            </div>
            
            <div class="all" style="border-radius: 5px; padding: 5px">
              <input 
              name="all"
              type="checkbox"
              class="knowledge-list"
              checked
              style="width: 20px; height: 20px;"
              v-model="CheckoutAllClass"
              @change="handleAllCheck"
              >
              <label 
              for="all"
              style="list-style: none;
              border-bottom: 1px solid #ccc;
              margin-top: 5px;
              width: 150px;
              display: inline-block;
              padding-bottom: 8px;
              font-size: 25px;
              text-align: center;"
              >All</label>
            </div>
            <button
              @click="submitClasses"
              style="
                width: 150px; 
                font-size: 20px;
                margin-top: 10px;
                margin-left: 17px;
                margin-bottom:10px;
                border-radius: 5px;
                background-color: #ccc;
                padding: 5px;
                color: #fff;
                font-weight: bold;
                border: none;
                cursor: pointer;
                "
            >Confirm filter</button>
          </form>
          
          
      </Dropdown>
    </div>
      

  </div>
  <div class="body">
    <div class="main">
      <div class="top">
        <!-- A. Scatter View -->
        <div class="scatter-view" v-if="clusterData">
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
import ScatterView from './components/ScatterView.vue'
import PortraitView from './components/PortraitView.vue'
import QuestionView from './components/QuestionView.vue'
import WeekView from './components/WeekView.vue'
import StudentView from './components/StudentView.vue'
import { mapActions, mapGetters } from 'vuex'
import Dropdown from 'v-dropdown'
import { filterClasses, getFilter } from './api/App'
export default {
  components: {
    ScatterView,
    PortraitView,
    QuestionView,
    WeekView,
    StudentView,
    Dropdown
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
      console.log('change!!!')
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
      console.log(response.data.data)
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
.app-container {
  width: 2100px;
  background-color: #ccc;
.header{
  width: 2100px;
  height: 50px;
  background-color: #2a2a2a;
  .title{
    float: left;
    color: #fff;
    font-size: 20px;
    font-weight: 700;
    margin-left: 20px;
    line-height: 50px;
  }
  .filter{
    float: right;
    margin-right: 20px;
    margin-top: 10px;
    width: 180px;
    height: 30px;
    border: none;
    outline: none;
    color: #fff;
    font-size: 20px;
    .v-dropdown-trigger{
      float: right;
      button{
        border: 0;
        width:100px;
        font-size: 18px;
        margin-top: 5px;
        margin-right: 5px;
        border-radius: 5px;
        border-bottom: 1px solid #fff;
        padding: 0;
      }   
    }
  }
}
.body {
  width: 2100px;
  height: 1230px;
  display: flex;
  .main{
    width: 1700px;
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
        width: 1300px;
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
        width: 1015px;
        height: 600px;
      }
    }
  }
  .panel{
    width: 400px;
    height: inherit;
  }
}

} //app-container
</style>
