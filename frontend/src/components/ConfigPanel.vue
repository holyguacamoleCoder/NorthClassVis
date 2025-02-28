<template>
  <div class="config-container">
    <div class="config-panel">
      <div class="config-panel-title">
        <div class="config-panel-title-icon"></div>
        <span class="config-panel-title-text">Cluster Configuration</span>
      </div>
      <Dropdown>
        <!-- trigger element -->
      <template #trigger>
        <DropdownTrigger>Class</DropdownTrigger>
      </template>
      <!-- contents display in dropdown -->
      <DropdownContent>
        classes
      </DropdownContent>  
      </Dropdown>

      <Dropdown>
        <!-- trigger element -->
      <template #trigger>
        <DropdownTrigger>Major</DropdownTrigger>
      </template>
      <!-- contents display in dropdown -->
      <DropdownContent>
        majors
      </DropdownContent>  
      </Dropdown>
    </div>
  </div>
  
</template>
  
<script>
import { Dropdown, DropdownContent, DropdownTrigger } from 'v-dropdown'
export default {
  name: 'ConfigPanel',
  components: {
   Dropdown,
   DropdownContent,
   DropdownTrigger
  },
  data() {
    return {
    }
  },
  mounted(){
  },
  methods: {
    
  }
};
</script>
  
<style scoped lang="less">
*{
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}
@config-panel-width: 500px;
@config-panel-height: 500px;
.config-container{
  z-index: 100;
  position: relative;
  height: @config-panel-height;
  width: @config-panel-width;
  top: 520px;
  left: 700px;
  border: 1px solid #ccc;
  border-radius: 8px;
  background-color: #fff;
  .config-panel-title{
    height: 50px;
    .config-panel-title-icon{
      float: left;
      height: 50px;
      width: 50px;
      background: no-repeat center/60% url('~@/assets/images/settings.png') #fff;
    }
    .config-panel-title-text{
      font-size: 20px;
      font-weight: bold;
      line-height: 50px;
    }
  }

  .dd-trigger{
    width: 150px;
    .dd-trigger-container .dd-default-trigger{
      width: 1500px !important;
      .dd-caret-down{
        margin-left: 50px;
      }
    }
  }
}
</style>
  