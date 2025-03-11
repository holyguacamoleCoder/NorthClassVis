import request from '@/utils/request'

// 获取周视图相关数据
export const getScatterData = () => {
  return request.get('/pca/scatter')
}