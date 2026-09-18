/** 顾客端接口（后端 /api/public/*，不需要登录） */
import { request } from './request'
import type { MenuRow, Order, StoreBrief } from './types'

/** 可点单的门店（后端只返回营业中的） */
export function getStores() {
  return request<{ stores: StoreBrief[] }>({ url: '/api/public/stores' })
}

/** 某门店的菜单（只含在售且本店上架的菜，价格是本店实际价） */
export function getMenu(storeId: number) {
  return request<{ dishes: MenuRow[] }>({
    url: `/api/public/stores/${storeId}/menu`,
  })
}

/** 下单时的一行明细——**只传菜品和数量，不传价格** */
export interface OrderItemPayload {
  dish_id: number
  quantity: number
  option_ids: number[]
}

/** 顾客自助下单 */
export function createOrder(data: {
  store_id: number
  source: string
  remark?: string
  items: OrderItemPayload[]
  /** 用哪张券（券包里的 id）；不传 = 不用券。**没登录的人手里没有券** */
  user_coupon_id?: number
}) {
  return request<Order>({ url: '/api/public/orders', method: 'POST', data })
}

/** 凭「单号 + 令牌」查订单详情 */
export function getOrder(orderNo: string, token: string) {
  return request<Order>({
    url: `/api/public/orders/${orderNo}`,
    params: { token },
  })
}

/** 模拟支付（真实对接微信支付要走 wx.requestPayment + 回调验签，见后端 wechat_pay.py） */
export function payOrder(orderNo: string, token: string, method = 'wechat') {
  return request<{ order: Order }>({
    url: `/api/public/orders/${orderNo}/pay`,
    method: 'POST',
    data: { method },
    params: { token },
  })
}

/** 顾客自己取消订单（只有门店还没接单、也还没付款时才能取消） */
export function cancelOrder(orderNo: string, token: string) {
  return request<Order>({
    url: `/api/public/orders/${orderNo}/cancel`,
    method: 'POST',
    params: { token },
  })
}
