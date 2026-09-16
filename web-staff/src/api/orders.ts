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

/** 下单时的一行明细（对应 OrderItemCreateSchema） */
export interface OrderItemPayload {
  dish_id: number
  quantity: number
  option_ids: number[]
}

/**
 * 下单请求体
 *
 * 注意这里**没有金额字段**——价格由后端按本店实际价 + 规格加价现算。
 * 前端算的价格只用来给收银员看，不参与下单。
 */
export interface OrderCreatePayload {
  store_id: number
  source?: string
  remark?: string
  /** 实际操作人；服务员用公用账号下单时必须传 */
  operator_id?: number
  /** 会员 id。**储值支付要靠它**——散客单扣不了任何人的余额 */
  member_id?: number
  items: OrderItemPayload[]
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

/** 下单（order:create）。必选规格没选、本店已下架、已停售都会被后端拒掉 */
export function createOrder(data: OrderCreatePayload) {
  return request<Order>({ url: '/orders', method: 'post', data })
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
