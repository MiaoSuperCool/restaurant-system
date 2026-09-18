import { request } from './request'
import type { ReportOverview } from './types'

/**
 * 经营概览（`report:store` 或 `report:all`，任一）
 *
 * 和电脑上那个报表页是**同一个接口**，只是这里只挑几块显示：
 * 手机上放得下「一共做了多少」和「哪家店做得好」，
 * 支付构成、菜品排行、时段分布那些还是回电脑上看。
 *
 * **数据范围在后端收窄**：店长只拿得到自己那家的数，
 * 传了别家的 `store_id` 会被 403 拦掉。
 */
export function getReportOverview(params: { days?: number; store_id?: number } = {}) {
  return request<ReportOverview>({
    url: '/api/reports/overview',
    method: 'GET',
    params,
  })
}