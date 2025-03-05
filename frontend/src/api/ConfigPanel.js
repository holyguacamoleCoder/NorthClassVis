import request from '@/utils/request'
import throttle from '@/utils/throttle'
export const setConfig = throttle((CheckoutClasses, CheckoutMajors) => {
  return request.post('/nav/config', {
    classes: CheckoutClasses,
    majors: CheckoutMajors
  })
})

export const getCOnfig = throttle(() => {
  return request.get('/nav/filter')
})