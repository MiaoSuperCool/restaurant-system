import { request } from './request'
import type { Pagination, Refund } from './types'

/** 退款列表接口返回的 data */
export interface RefundListData {
  refunds: Refund[]
  pagination: Pagination
}

/** 发起退款申请的请求体（对应 RefundCreateSchema） */
export interface RefundApplyPayload {
  amount: number
  /** 必填——留痕的用途就在这里 */
  reason: string
  /** online 线上退款 / offline 线下补录（钱已经用现金退了，事后补录） */
  type?: string
}

/** 退款单列表（受数据范围限制：店长只看得到本店订单的退款） */
export function getRefunds(params: {
  search?: string
  page?: number
  store_id?: number
  status?: string
}) {
  return request<RefundListData>({ url: '/refunds', method: 'get', params })
}

/**
 * 对某个订单发起退款申请
 *
 * 这一步只产生「流程」，钱一分没动——要再走审批和确认打款。
 */
export function applyRefund(orderId: number, data: RefundApplyPayload) {
  return request<Refund>({ url: `/refunds/orders/${orderId}`, method: 'post', data })
}

/** 批准退款（refund:approve；超过限额还需要 refund:approve:large，由后端判断） */
export function approveRefund(id: number, remark = '') {
  return request<Refund>({ url: `/refunds/${id}/approve`, method: 'post', data: { remark } })
}

/** 驳回退款（必须写原因） */
export function rejectRefund(id: number, remark: string) {
  return request<Refund>({ url: `/refunds/${id}/reject`, method: 'post', data: { remark } })
}

/** 确认退款完成：钱真的出去了，记一条退款流水 */
export function settleRefund(id: number, data: { method?: string; transaction_no?: string }) {
  return request<Refund>({ url: `/refunds/${id}/settle`, method: 'post', data })
}
