import request from '@/utils/request'

// 获取学生视图相关数据
export const getStudents = (selectedIds) => {
  return request.get('student/tree_data',selectedIds ? {
    params: {
      student_ids: selectedIds
    }
  } : null)
}