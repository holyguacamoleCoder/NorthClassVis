import axios from 'axios'
const instance = axios.create({
  baseURL: 'http://localhost:5000/api/',
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

// // 添加响应拦截器
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
