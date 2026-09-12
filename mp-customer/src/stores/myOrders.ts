/**
 * 我在本机下过的单
 *
 * 一期顾客不登录（会员是二期的事），所以服务端没有「我的订单列表」这个接口——
 * 它不知道你是谁。本地存一份「单号 + 查询令牌」，进「我的订单」页时
 * 拿这些凭据去逐个查详情。
 *
 * 卸载小程序或换手机之后这份记录就没了——**这正是二期要做会员登录的原因之一**。
 */
import type { Order } from '@/api/types'

const STORAGE_KEY = 'my_orders'

export interface MyOrderBrief {
  order_no: string
  query_token: string
  store_name: string
  payable_amount: number
  created_at: string
}

export function saveOrder(order: Order) {
  const list = getMyOrders().filter((item) => item.order_no !== order.order_no)
  list.unshift({
    order_no: order.order_no,
    query_token: order.query_token,
    store_name: order.store_name || '',
    payable_amount: order.payable_amount,
    created_at: order.created_at || '',
  })
  // 只留最近 20 单，免得 storage 越堆越大
  uni.setStorageSync(STORAGE_KEY, JSON.stringify(list.slice(0, 20)))
}

export function getMyOrders(): MyOrderBrief[] {
  try {
    return JSON.parse((uni.getStorageSync(STORAGE_KEY) as string) || '[]')
  } catch {
    return []
  }
}

export function findMyOrder(orderNo: string): MyOrderBrief | undefined {
  return getMyOrders().find((item) => item.order_no === orderNo)
}
