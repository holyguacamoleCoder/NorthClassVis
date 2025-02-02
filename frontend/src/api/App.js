import request from '@/utils/request'

export const filterClasses = (checkoutClasses) => {
  return request.post('/filter_classes', {
    classes: checkoutClasses
  })
}

export const getFilter = () => {
  return request.get('/filter')
}