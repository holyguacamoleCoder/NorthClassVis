<template>
<div class="header-container">
  <div class="left-label">
    <div class="title">NorthClassVision</div>
    <div class="icon-radar">icon</div>
  </div>
  
  <div class="right-label">
    <div class="filter">
    <Dropdown>
      <!-- trigger element -->
      <template #trigger>
        <button type="button" style="font-weight: bold">
          {{displayButton}}
        </button>
      </template>
      <!-- contents display in dropdown -->
      <DropdownContent>
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
      </DropdownContent>  
        
    </Dropdown>
    </div>
    <div class="display-options">
      <div class="option-major">
        <span>Major:</span>
        <div class="text-content">All</div>
      </div>
      <div class="option-class">
        <span>Class:</span>
        <div class="text-content">All</div>
      </div>
    </div>
    <div class="config-button">
      icon
    </div>
  </div>

</div>

</template>

<script>
import { Dropdown, DropdownContent } from 'v-dropdown'
export default {
  name: 'HeaderConfig',
  components: {
    Dropdown,
    DropdownContent
  },
  data() {
    return {
    }
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
@total_width : 2300px;
.header-container{
  position: relative;
  width: @total_width;
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
      margin-left: 20px;
      line-height: 50px;
    }
    .icon-radar{
      float: left;
    }
  }
  .right-label{
    position: absolute;
    top: 50%;
    right: 0;
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
      margin-left: 20px;
      background-color: #fff;
      border-radius: 100%;
      height: 42px;
      width: 42px;
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
      .dd-trigger{
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
}
</style>
