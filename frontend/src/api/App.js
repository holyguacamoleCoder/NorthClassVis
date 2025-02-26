import request from '@/utils/request'
import throttle from '@/utils/throttle'
export const filterClasses = throttle((checkoutClasses) => {
  return request.post('/filter_classes', {
    classes: checkoutClasses
  })
})

export const getFilter = throttle(() => {
  return request.get('/filter')
})