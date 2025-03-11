import request from '@/utils/request'

// 获取问题视图相关数据
export const getQuestions = () => {
  return request.get('/question/questions')
}