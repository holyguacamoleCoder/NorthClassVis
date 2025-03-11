import request from '@/utils/request'
// import debounce from '@/utils/debounce'
// import throttle from '@/utils/throttle'

// 设置后台管理班级数据 
export const setConfig = (CheckoutClasses, CheckoutMajors) => {
  return request.post('/nav/config', {
    classes: CheckoutClasses,
    majors: CheckoutMajors
  })
}

// 获取后台管理班级数据
export const getConfig = () => {
  return request.get('/nav/filter')
}