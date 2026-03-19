import request from '@/utils/request'
// import debounce from '@/utils/debounce'
// import throttle from '@/utils/throttle'

// 设置后台管理班级数据，weekRange 可选 [startWeek, endWeek]
export const setConfig = (CheckoutClasses, CheckoutMajors, weekRange = null) => {
  const body = { classes: CheckoutClasses, majors: CheckoutMajors }
  if (weekRange && Array.isArray(weekRange) && weekRange.length >= 2) {
    body.week_range = [Number(weekRange[0]), Number(weekRange[1])]
  }
  return request.post('/nav/config', body)
}

// 获取后台管理班级数据
export const getConfig = () => {
  return request.get('/nav/filter')
}