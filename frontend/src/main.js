import { createApp } from 'vue'
import App from './App.vue'
import store from './store'
import * as echarts from 'echarts'
import * as d3 from 'd3'

// import Simplebar from 'simplebar-vue'
// import 'simplebar-vue/dist/simplebar.min.css'


const app = createApp(App)
app.use(store)
app.mount('#app')
app.config.globalProperties.$echarts = echarts
app.config.globalProperties.$d3 = d3
//滚动条组件
// app.use(simplebar)
