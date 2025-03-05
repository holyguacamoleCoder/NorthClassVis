import request from '@/utils/request'
import throttle from '@/utils/throttle'
export const filterClasses = throttle((checkoutClasses) => {
  return request.post('/nav/config', {
    classes: checkoutClasses
  })
})

export const getFilter = throttle(() => {
  return request.get('/nav/filter')
})