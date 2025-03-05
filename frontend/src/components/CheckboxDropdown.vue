<template>
  <Dropdown>
    <template #trigger>
      <DropdownTrigger>
        <div class="tag">{{ title }}</div>
        {{ displayDropDownText(allChecked, items) }}
      </DropdownTrigger>
    </template>
    <DropdownContent>
      <form :id="title.toLowerCase()" class="checkboxs" :name="`${title}Form`">
        <div class="checkbox-list" v-for="(item, index) in items" :key="index">
          <input type="checkbox" class="checkbox-input" :checked="item.checked"
            :name="item.text" v-model="item.checked" @change="handleCheck">
          <label class="checkbox-label">{{ item.text }}</label>
        </div>
        <div class="checkbox-for-all">
          <input name="all" type="checkbox" class="checkbox-input"
            :checked="allChecked" v-model="allChecked" @change="handleAllCheck">
          <label for="all" class="checkbox-label">All</label>
        </div>
      </form>
    </DropdownContent>
  </Dropdown>
</template>

<script>
import { Dropdown, DropdownContent, DropdownTrigger } from 'v-dropdown'
export default {
  name: 'CheckboxDropdown',
  components: {
    Dropdown,
    DropdownContent,
    DropdownTrigger,
  },
  props: ['items', 'title', 'text'],
  computed: {
    allChecked: {
      get() {
        return this.items.every(item => item.checked);
      },
      set(value) {
        this.items.forEach(item => item.checked = value);
      }
    }
  },
  methods: {
    displayDropDownText(checkoutAllData, selectedData) {
      if (checkoutAllData) return 'All'
      const selectedExist = selectedData.some(d => d.checked === true)
      if (selectedExist) return 'Part'
      else return 'None'
    },
    handleCheck(event) {
      if (!event.target.checked) {
        this.allChecked = false
      }
      this.$emit('change', 
      this.items.filter(item => item.checked).map(item => item.text),
      this.displayDropDownText(this.allChecked, this.items))
    },
    handleAllCheck(event) {
      const isChecked = event.target.checked
      this.items.forEach(item => item.checked = isChecked)
      this.$emit('change', 
      isChecked ? this.items.map(item => item.text) : [],
      this.displayDropDownText(this.allChecked, this.items))
    }
  }
};
</script>

<style scoped lang="less">
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