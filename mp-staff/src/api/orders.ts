import { request } from './request'
import type { GrouponVoucher, Order, Pagination } from './types'

export interface OrderListData {
  orders: Order[]
  pagination: Pagination
}

/** 下单时的一行明细——**只传菜品和数量，不传价格**，价格一律后端现算 */
export interface OrderItemPayload {
  dish_id: number
  quantity: number
  option_ids: number[]
}

export interface OrderCreatePayload {
  store_id: number
  source?: string
  remark?: string
  member_id?: number
  coupon_id?: number
  points_to_use?: number
  items: OrderItemPayload[]
}

/**
 * 订单列表（order:view）。数据范围由后端按角色收窄：店长只看得到本店
 *
 * **永远带上菜品明细**（`with_items=1`）：这个端拿订单列表就是为了干活——
 * 出单页要的是「做什么菜」，只有单号和金额的单子后厨没法做。
 * 网页端的订单列表反而不带，那边只要汇总，白查一遍明细是浪费。
 *
 * 传 1 不传 true：后端用 marshmallow 的 Boolean 接这个参数，1/0 是它认的写法，
 * 而且不同端拼 query string 的行为略有出入，数字最稳。
 */
export function getOrders(params: {
  page?: number
  per_page?: number
  search?: string
  store_id?: number
  status?: string
}) {
  return request<OrderListData>({
    url: '/api/orders',
    method: 'GET',
    params: { with_items: 1, ...params },
  })
}

/** 订单详情 */
export function getOrder(id: number) {
  return request<Order>({ url: `/api/orders/${id}`, method: 'GET' })
}

/** 代客下单（order:create） */
export function createOrder(data: OrderCreatePayload) {
  return request<Order>({ url: '/api/orders', method: 'POST', data })
}

/** 接单：待接单 → 已接单（order:receive） */
export function acceptOrder(id: number) {
  return request<Order>({ url: `/api/orders/${id}/accept`, method: 'POST' })
}

/** 完成：已接单 → 已完成（order:receive） */
export function completeOrder(id: number) {
  return request<Order>({ url: `/api/orders/${id}/complete`, method: 'POST' })
}

/**
 * 核销团购券（coupon:verify）
 *
 * 核销是**挂在订单上**的：券是用来抵这一单的钱的，所以要先有单子。
 * 一次做两件事：记一条核销记录（月底拿去和美团/抖音对账）+ 记一笔收款。
 * 同一个券码核销第二次会被拒（数据库上有唯一约束兜底）。
 */
export function verifyGroupon(
  orderId: number,
  data: { code: string; platform: string; amount: number }
) {
  return request<{ voucher: GrouponVoucher; order: Order }>({
    url: `/api/orders/${orderId}/vouchers`,
    method: 'POST',
    data,
  })
}