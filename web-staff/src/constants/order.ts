/**
 * 订单相关枚举选项
 *
 * 取值必须与 backend/app/models/order.py、payment.py 的常量保持一致。
 * 展示用的中文名不在这里查：列表数据里后端已经带了 xxx_label 字段。
 */
import type { EnumOption } from './store'

export const ORDER_STATUS_OPTIONS: EnumOption[] = [
  { value: 'pending', label: '待接单' },
  { value: 'accepted', label: '已接单' },
  { value: 'completed', label: '已完成' },
  { value: 'cancelled', label: '已取消' },
]

export const ORDER_SOURCE_OPTIONS: EnumOption[] = [
  { value: 'dine_in', label: '堂食' },
  { value: 'takeaway', label: '自取' },
  { value: 'delivery', label: '外卖' },
]

export const PAYMENT_METHOD_OPTIONS: EnumOption[] = [
  { value: 'wechat', label: '微信支付' },
  { value: 'cash', label: '现金' },
  { value: 'balance', label: '储值' },
  { value: 'groupon', label: '团购券' },
]

/** 订单状态 → el-tag 的 type。待接单用 danger，让收银员一眼看到要处理的单子 */
export const ORDER_STATUS_TAG: Record<string, string> = {
  pending: 'danger',
  accepted: 'warning',
  completed: 'success',
  cancelled: 'info',
}
