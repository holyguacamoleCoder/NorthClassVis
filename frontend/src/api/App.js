import request from '@/utils/request'

// 获取周视图相关数据
export const filterClasses = (checkoutClasses) => {
  return request.post('/filter_classes', {
    classes: checkoutClasses
  })
}

export const getFilter = () => {
  return request.get('/filter')
}