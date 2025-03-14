<template>
  <div class="config-container">
    <div class="config-panel">
      <LoadingSpinner v-if="loading" />

      <div class="config-panel-title">
        <div class="config-panel-title-icon"></div>
        <span class="config-panel-title-text">Cluster Configuration</span>
      </div>
      <div class="config-panel-checkbox">
        <CheckboxDropdown v-if="CheckoutClasses" :items="CheckoutClasses" title="Class" @change="updateSelectedClasses"/>
        <CheckboxDropdown v-if="CheckoutMajors" :items="CheckoutMajors" title="Major" @change="updateSelectedMajors"/>
      </div>

      <div class="config-panel-main">
        <button class="close-button" @click="closePanel">Close</button>
        <button class="submit-button" @click="submitConfigData">Submit</button>
      </div>
    </div>
  </div>
</template>

<script>
import config from '@/assets/config/config.json'
import CheckboxDropdown from './CheckboxDropdown.vue'
import LoadingSpinner from './LoadingSpinner.vue'
import { setConfig, getConfig } from '@/api/ConfigPanel.js'
import { mapActions } from 'vuex'
export default {
  name: 'ConfigPanel',
  components: {
    CheckboxDropdown,
    LoadingSpinner
  },
  data() {
    return {
      loading: false,
      CheckoutClasses: [],
      CheckoutMajors: [],
      displayClassesText: 'Part',
      displayMajorsText: 'All'
    }
  },
  async created(){
    const response = await getConfig()
    if (response.status === 200) {
      const backendClasses = response.data.classes
      const backendMajors = response.data.majors

      // 初始化所有项为 checked: false
      this.CheckoutClasses = config.classes.map(item => ({
        text: item.text,
        checked: backendClasses.includes(item.text)
      }))

      this.CheckoutMajors = config.majors.map(item => ({
        text: item.text,
        checked: backendMajors.includes(item.text)
      }))
      console.log('Config loaded successfully');
    } else {
      console.error('Failed to fetch config data:', response);
    }
  },
  mounted(){
  },
  computed: {
    // ...mapState(['configLoaded']),
  },
  methods: {
    ...mapActions(['updateConfig']),
    updateSelectedClasses(selectedClasses, text) {
      this.displayClassesText = text
    },
    updateSelectedMajors(selectedMajors, text) {
      this.displayMajorsText = text
    },
    async submitConfigData(){
      const selectedClasses = this.CheckoutClasses.filter(item => item.checked).map(item => item.text)      
      const selectedMajors = this.CheckoutMajors.filter(item => item.checked).map(item => item.text)
      if(selectedClasses.length === 0){
        alert('Please select at least one class.')
        return
      }
      if(selectedMajors.length === 0) {
        alert('Please select at least one major.')
        return
      }
      console.log('Selected Classes:', selectedClasses)
      console.log('Selected Majors:', selectedMajors)
      this.loading =  true
      const data  = await setConfig(selectedClasses, selectedMajors)
      if(data.status === 200){
        console.log('Config updated successfully')
        // this.closePanel()
        this.$store.commit('SET_CONFIG_LOADED', Date.now()); // 重置状态以触发重新加载
        this.loading = false
        this.closePanel()
      }
    },
    closePanel() {
      this.$emit('close', this.displayClassesText, this.displayMajorsText)
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
@config-panel-width: 400px;
@config-panel-height: 250px;
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
    margin-bottom: 10px;
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
    
  }
  .config-panel-main{
    .close-button
    ,.submit-button{
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

</style>