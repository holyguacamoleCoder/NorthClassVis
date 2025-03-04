<template>
<div class="header-container">
  <div class="left-label">
    <div class="icon-radar">
      <IconBlock/>
    </div>
    <div class="title">NorthClassVis</div>
  </div>
  
  <div class="right-label">
    <div class="display-options">
      <div class="option-class">
        <span>Class:</span>
        <div class="text-content">{{ selectedClasses }}</div>
      </div>
      <div class="option-major">
        <span>Major:</span>
        <div class="text-content">{{ selectedMajors }}</div>
      </div>
    </div>
    <div class="config-button" @click="toggleConfigPanel"></div>
    <div class="cluster-button">CLUSTER</div>
  </div>
  
  <ConfigPanel 
    v-if="isConfigPanelVisible"
    @close="hideConfigPanel"
    :selectedClasses="selectedClasses"
    :selectedMajors="selectedMajors"
  />

</div>

</template>

<script>
import IconBlock from '@/components/IconBlock.vue'
import ConfigPanel from './ConfigPanel.vue'
export default {
  name: 'HeaderConfig',
  components: {
    IconBlock,
    ConfigPanel,
  },
  data() {
    return {
      isConfigPanelVisible: false,
      selectedClasses: 'None',
      selectedMajors: 'None',
    }
  },
  created(){
  },
  methods: {
   toggleConfigPanel(){
      this.isConfigPanelVisible = !this.isConfigPanelVisible;
    },
    hideConfigPanel(classesText, majorsText){
      this.isConfigPanelVisible = false;
      this.selectedClasses = classesText
      this.selectedMajors = majorsText
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
.header-container{
  position: relative;
  height: 50px;
  background-color: #2a2a2a;
  border-radius: 5px 5px 0 0;
  .left-label{
    float: left;
    .title{
      float: left;
      color: #fff;
      font-size: 20px;
      font-weight: 700;
      margin-left: 4px;
      line-height: 50px;
    }
    .icon-radar{
      float: left;
    }
  }
  .right-label{
    position: absolute;
    top: 50%;
    right: 3px;
    transform: translateY(-50%);
    padding: 0 20px 0 0;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    .display-options{      
      display: flex;
      align-items: center;
      [class^="option-"]{
        color: #fff;
        padding: 0 20px;
        font-size: 17px;
        display: flex;
        align-items: center;
        span{
          padding: 0 20px 0 0;
        }
        .text-content{
          padding: 0 30px;
          border-bottom: 1px solid #fff;
        }
      }
    }
    .config-button{
      position: relative;
      margin-left: 20px;
      background-color: #fff;
      background: no-repeat center/60% url('~@/assets/images/settings.png') #fff;
      border-radius: 100%;
      height: 40px;
      width: 40px;
    }
    .cluster-button{
      margin-left: 40px;
      padding: 4px 10px;
      font-weight: bold;
      border-radius: 5px;
      background-color: #fff;
    }
  }
}

.config-container {
  position: absolute; /* 绝对定位 */
  top: 53px; /* 距离 config-button 底部的距离 */
  right: -70px; /* 距离 config-button 左侧的距离 */
  z-index: 100; /* 确保 ConfigPanel 在其他元素之上 */
}
</style>
