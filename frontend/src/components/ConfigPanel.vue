<template>
  <div class="config-container">
    <div class="config-panel">
      <div class="config-panel-title">
        <div class="config-panel-title-icon"></div>
        <span class="config-panel-title-text">Cluster Configuration</span>
      </div>
      <div class="config-panel-checkbox">
        <Dropdown>
          <template #trigger>
            <DropdownTrigger>
              <div class="tag">Class</div>
              {{ displayDropDownText(CheckoutAllClass, CheckoutClasses) }}
            </DropdownTrigger>
          </template>
          <DropdownContent>
          <form id="classes" class="checkboxs" name="myForm">
            <div class="checkbox-list" v-for="(item, index) in CheckoutClasses" :key="index">
              <input class="checkbox-input" type="checkbox" :checked="item.checked"
                :name="item.text" v-model="item.checked" @change="handleCheck">
              <label class="checkbox-label">{{ item.text }}</label>
            </div>
            <div class="checkbox-for-all">
              <input name="all" type="checkbox" class="checkbox-input" 
                :checked="CheckoutAllClass" v-model="CheckoutAllClass" @change="handleAllCheck">
              <label for="all" class="checkbox-label">All</label>
            </div>
          </form>
          </DropdownContent>  
        </Dropdown>
      
        <Dropdown>
          <template #trigger>
            <DropdownTrigger>
              <div class="tag">Major</div>
              {{ displayDropDownText(CheckoutAllMajor, CheckoutMajors) }}
            </DropdownTrigger>
          </template>
          <DropdownContent>
            <form id="majors" class="checkboxs" name="majorForm">
              <div class="checkbox-list" v-for="(item, index) in CheckoutMajors" :key="index">
                <input type="checkbox" class="checkbox-input" :checked="item.checked"
                  :name="item.text" v-model="item.checked" @change="handleMajorCheck">
                <label class="checkbox-label">{{ item.text }}</label>
              </div>
              <div class="checkbox-for-all">
                <input name="all" type="checkbox" class="checkbox-input"
                  :checked="CheckoutAllMajor" v-model="CheckoutAllMajor"  @change="handleAllMajorCheck">
                <label for="all" class="checkbox-label">All</label>
              </div>    
            </form>
          </DropdownContent>  
        </Dropdown>
      </div>

      <div class="config-panel-main">
        <button class="confirm-button" @click="confirmAndClose">Confirm</button>
      </div>
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
      CheckoutClasses: [
        { text: 'Class A', checked: false },
        { text: 'Class B', checked: false },
        { text: 'Class C', checked: false }
      ],
      CheckoutMajors: [
        { text: 'Major A', checked: false },
        { text: 'Major B', checked: false },
        { text: 'Major C', checked: false }
      ],
      CheckoutAllClass: false,
      CheckoutAllMajor: false,
    }
  },
  mounted(){
  },
  computed: {
    
  },
  methods: {
    displayDropDownText(checkoutAllData, selectedData) {
      if (checkoutAllData) return 'All'
      const selectedExist = selectedData.some(d => d.checked === true)
      if (selectedExist) return 'Part'
      else return 'None'
    },
    handleCheck(event) {
      const isChecked = event.target.checked
      if (!isChecked) {
        this.CheckoutAllClass = false
      }
    },
    handleAllCheck(event) {
      const isChecked = event.target.checked;
      this.CheckoutClasses.forEach(item => {
        item.checked = isChecked;
      })
    },
    handleMajorCheck(event) {
      const isChecked = event.target.checked
      if (!isChecked) {
        this.CheckoutAllMajor = false
      }
    },
    handleAllMajorCheck(event) {
      const isChecked = event.target.checked;
      this.CheckoutMajors.forEach(item => {
        item.checked = isChecked
      })
    },
    submitClasses() {
      const selectedClasses = this.CheckoutClasses.filter(item => item.checked).map(item => item.text);
      console.log('Selected Classes:', selectedClasses);
      // 这里可以添加发送请求到后端的代码
    },
    submitMajors() {
      const selectedMajors = this.CheckoutMajors.filter(item => item.checked).map(item => item.text);
      console.log('Selected Majors:', selectedMajors);
      // 这里可以添加发送请求到后端的代码
    },
    confirmAndClose() {
      const classesText = this.displayDropDownText(this.CheckoutAllClass, this.CheckoutClasses)
      const majorsText = this.displayDropDownText(this.CheckoutAllMajor, this.CheckoutMajors)
      this.$emit('close', classesText, majorsText)
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
@config-panel-width: 600px;
@config-panel-height: 500px;
.config-container{
  z-index: 100;
  position: relative;
  height: @config-panel-height;
  width: @config-panel-width;
  border: 1px solid #ccc;
  border-radius: 10px;
  background-color: #fff;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1); /* 添加阴影 */
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
  .config-panel-checkbox{
    height: 80px;
    padding: 10px 30px;
    .dd-trigger{
      width: 150px;
      .dd-trigger-container{
        position: relative;
        .dd-default-trigger{
          width: 1500px !important;
          .dd-caret-down{
            margin-left: 50px;
          }
        }
        .tag{
          position: absolute;
          top: -25%;
          font-size: 12px;
          background-color: #fff;
          color: #ccc;
          padding: 0 5px;
        }
      }
    }
  }
  .config-panel-main{
    .confirm-button{
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
    }
  }
}
.checkboxs {
  .checkbox-list,
  .checkbox-for-all {
    border-radius: 5px;
    padding: 5px;
    width: 180px;
    display: flex;
    align-items: center;
    margin-bottom: 10px;
    .checkbox-input {
      width: 20px;
      height: 20px;
    }
    .checkbox-label {
      list-style: none;
      margin-top: 0;
      display: inline-block;
      width: 150px;
      margin: 10px 0;
      font-size: 20px;
      text-align: center;
    }
  }
}
</style>