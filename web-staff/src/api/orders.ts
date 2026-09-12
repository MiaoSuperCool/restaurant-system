import { request } from './request'
import type { Order, Pagination, Payment } from './types'

/** 订单列表接口返回的 data */
export interface OrderListData {
  orders: Order[]
  pagination: Pagination
}

/** 收款接口返回的 data */
export interface CollectResult {
  payment: Payment
  order: Order
}

/** 收款请求体（对应 PaymentCreateSchema） */
export interface CollectPayload {
  method: string
  amount: number
  /** 第三方流水号；现金留空 */
  transaction_no?: string
}

/** 订单列表（受数据范围限制：店长只看得到本店） */
export function getOrders(params: {
  search?: string
  page?: number
  store_id?: number
  status?: string
}) {
  return request<OrderListData>({ url: '/orders', method: 'get', params })
}

/** 订单详情（含明细、规格、支付记录） */
export function getOrder(id: number) {
  return request<Order>({ url: `/orders/${id}`, method: 'get' })
}

/** 接单：待接单 → 已接单（order:receive） */
export function acceptOrder(id: number) {
  return request<Order>({ url: `/orders/${id}/accept`, method: 'post' })
}

/** 完成：已接单 → 已完成（order:receive） */
export function completeOrder(id: number) {
  return request<Order>({ url: `/orders/${id}/complete`, method: 'post' })
}

/** 取消订单（order:cancel；已收款的单子会被后端拦住） */
export function cancelOrder(id: number) {
  return request<Order>({ url: `/orders/${id}/cancel`, method: 'post' })
}

/** 记一笔收款（pay:collect）。一个订单可以多次调用：组合支付、先定金后尾款 */
export function collectPayment(id: number, data: CollectPayload) {
  return request<CollectResult>({ url: `/orders/${id}/payments`, method: 'post', data })
}
