import { request } from './request'
import type { Staff } from './types'

/** 今日经营看板（受数据范围限制：店长看到的是本店数据） */
export interface TodayStats {
  order_count: number
  /** 今天真收到手的钱；取消的单子不算 */
  revenue: number
  pending_count: number
}

/** 首页数据：登录态（与登录接口同一份结构）+ 今日看板 */
export interface DashboardData {
  staff: Staff
  permissions: string[]
  data_scope: string
  today: TodayStats
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