import request from '@/utils/request'

export const getClusterStudents = () => {
  return request.get('/cluster/students')
}