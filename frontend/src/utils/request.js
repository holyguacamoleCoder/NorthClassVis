import axios from 'axios'

// 使用环境变量，不写死地址与端口。开发时由 devServer 代理 /api，生产时由 Nginx 反代
const baseURL = process.env.VUE_APP_API_BASE_URL ?? '/api'

const instance = axios.create({
  baseURL,
  timeout: 40000
})

// 自定义配置
// 请求/响应拦截器
// 添加请求拦截器
instance.interceptors.request.use(function (config) {
  return config
}, function (error) {
  // 对请求错误做些什么
  return Promise.reject(error)
})

// 响应拦截器：对 cluster 相关接口在 500/503 时自动重试（FeatureFactory 尚未就绪）
const CLUSTER_RETRY_MAX = 3
const CLUSTER_RETRY_DELAY_MS = 3000

instance.interceptors.response.use(
  function (response) {
    return response
  },
  async function (error) {
    const config = error.config
    if (!config || config.__clusterRetryCount >= CLUSTER_RETRY_MAX) {
      return Promise.reject(error)
    }
    if (config.method && config.method.toLowerCase() !== 'get') {
      return Promise.reject(error)
    }
    const status = error.response?.status
    if (status !== 500 && status !== 503) {
      return Promise.reject(error)
    }
    const url = config.url || ''
    if (!url.includes('cluster/everyone') && !url.includes('cluster/students')) {
      return Promise.reject(error)
    }
    config.__clusterRetryCount = (config.__clusterRetryCount || 0) + 1
    await new Promise(r => setTimeout(r, CLUSTER_RETRY_DELAY_MS))
    return instance.request(config)
  }
)

// // 添加响应拦截器（原注释保留）
// instance.interceptors.response.use(function (response) {
//   const res = response.data
//   if (res.status !== 200) {
//     return Promise.reject(new Error(res.message))
//   } else {
//     // 关闭loading
//   }
//   return res
// }, function (error) {
//   // 超出 2xx 范围的状态码都会触发该函数。
//   // 对响应错误做点什么
//   return Promise.reject(error)
// })

// 导出
export default instance
