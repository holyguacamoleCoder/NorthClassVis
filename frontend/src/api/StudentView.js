import request from '@/utils/request'

// 获取周视图相关数据
export const getStudents = () => {
  return request.get('student/tree_data',{
    params: {
      // limit: 10
    }
  })
}