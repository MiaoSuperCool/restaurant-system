import { request } from './request'
import type { Staff } from './types'

/** 首页数据（模板通用：新项目在这里扩展你的首页结构） */
export interface DashboardData {
  staff: Staff
  is_admin: boolean
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