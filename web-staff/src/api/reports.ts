import { request } from './request'

/** 汇总：这一段时间的经营结果 */
export interface ReportSummary {
  revenue: number
  order_count: number
  /** 客单价 = 营业额 ÷ 单量；单量为 0 时后端给 0，不是 NaN */
  avg_order_amount: number
  refund_amount: number
  cancelled_count: number
}

/** 按天的一格。**没有单的日子也有一行**，不然柱子会跳着排 */
export interface ReportTrendRow {
  date: string
  revenue: number
  order_count: number
}

/** 按时段的一格（本地时间的小时）。只返回有单的小时 */
export interface ReportHourRow {
  hour: number
  order_count: number
  revenue: number
}

/** 按门店的一格。店长只会看到自己一家 */
export interface ReportStoreRow {
  store_id: number
  store_name: string
  revenue: number
  order_count: number
}

/** 支付方式构成。只看成功的流水 */
export interface ReportMethodRow {
  method: string
  method_label: string
  count: number
  amount: number
}

/** 菜品排行（按份数，取前 10） */
export interface ReportDishRow {
  dish_id: number
  dish_name: string
  quantity: number
  amount: number
}

export interface ReportOverview {
  range: { start: string; end: string; days: number }
  summary: ReportSummary
  trend: ReportTrendRow[]
  by_hour: ReportHourRow[]
  by_store: ReportStoreRow[]
  by_method: ReportMethodRow[]
  top_dishes: ReportDishRow[]
}

/**
 * 经营概览（`report:store` 或 `report:all`，任一）
 *
 * **数据范围在后端收窄**：店长传了别家的 `store_id` 会被 403 拦掉，
 * 不传则只统计他自己那家。前端不用管这件事——也管不了。
 */
export function getReportOverview(params: {
  days?: number
  start?: string
  end?: string
  store_id?: number
}) {
  return request<ReportOverview>({
    url: '/reports/overview',
    method: 'get',
    params,
  })
}