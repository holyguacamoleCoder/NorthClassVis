import request from '@/utils/request'

// 获取被选中学生的各个指标数据
export const getSelectedData = (selectedStudent) => {
  return request.get('/cluster/display', { 
    params: {
      student_ids: selectedStudent
    } 
  })
}