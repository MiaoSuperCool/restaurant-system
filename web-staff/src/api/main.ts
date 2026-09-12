import { request } from './request'
import type { Staff } from './types'

/** 首页数据：登录态（与登录接口同一份结构）+ 示例统计 */
export interface DashboardData {
  staff: Staff
  permissions: string[]
  data_scope: string
  staff_count: number
  store_count: number
}

/**
 * 首页数据接口
 * 注意：这个接口在根路径 /index（不在 /api 下），
 * 所以临时把 baseURL 置空，由 Vite 代理/Flask 托管转发。
 */
export function getDashboard() {
  return request<DashboardData>({
    url: '/index',
    baseURL: '',
    method: 'get',
  })
}