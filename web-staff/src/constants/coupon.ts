/**
 * 优惠券枚举选项 + 几句「把数据说成人话」的小工具
 *
 * 取值必须与 backend/app/models/coupon.py 里的常量保持一致——
 * 后端 schema 用 validate.OneOf 卡这些值，传错了会返回 422。
 */
import type { EnumOption } from './store'

export const COUPON_TYPE_OPTIONS: EnumOption[] = [
  { value: 'full_cut', label: '满减' },
  { value: 'discount', label: '折扣' },
]

/** 券**模板**的状态：启用 / 停用（停用只停发，发出去的照常能用） */
export const COUPON_TEMPLATE_STATUS_OPTIONS: EnumOption[] = [
  { value: 'active', label: '启用' },
  { value: 'disabled', label: '停用' },
]

/** 券模板状态 → el-tag 的 type */
export const COUPON_STATUS_TAG: Record<string, string> = {
  active: 'success',
  disabled: 'info',
}

/**
 * 顾客手上那张券的状态 → el-tag 的 type
 *
 * 后两个（已过期 / 未生效）**是算出来的**，库里没有这两个状态——
 * 所以颜色也要在算出来的那一刻才定得下来（见 models/coupon.py 开头）。
 */
export const USER_COUPON_STATUS_TAG: Record<string, string> = {
  unused: 'success',
  used: 'info',
  expired: 'info',
  not_started: 'warning',
}

/** 会员券包页签用的四档状态（和 `CouponService.get_member_coupons` 的 status 参数对齐） */
export const USER_COUPON_FILTERS: EnumOption[] = [
  { value: 'unused', label: '可用' },
  { value: 'used', label: '已用' },
  { value: 'expired', label: '已过期' },
  { value: 'not_started', label: '未生效' },
]

/**
 * 券的样子：券模板和用户持券都符合它
 *
 * **类型字段两个名字都得认**：券模板（CouponTemplate）上叫 `type`，
 * 用户手里那张券（UserCoupon）上叫 `template_type`——后者是「这张券用的是
 * 哪种模板」。只认一个的话，折扣券会被当成满减，显示成「满 ¥50 减 ¥0.85」。
 */
interface CouponLike {
  type?: string
  template_type?: string
  value: number
  min_amount: number
}

/** 折扣率 → 「8.5」这种给人看的数字（0.85 → 8.5 折，不是「减 15%」） */
function discountRate(value: number): string {
  return String(Number((value * 10).toFixed(1)))
}

function couponType(coupon: CouponLike): string {
  return coupon.type ?? coupon.template_type ?? ''
}

/** 券的一句话描述，如「满 ¥100 减 ¥20」「满 ¥50 打 8.5 折」 */
export function describeCoupon(coupon: CouponLike): string {
  const threshold = coupon.min_amount > 0 ? `满 ¥${coupon.min_amount.toFixed(0)}` : '无门槛'
  if (couponType(coupon) === 'discount') {
    return `${threshold} 打 ${discountRate(coupon.value)} 折`
  }
  return `${threshold} 减 ¥${coupon.value.toFixed(2)}`
}

/** 券在列表里显示的「值」——满减是金额，折扣是折扣率 */
export function couponValueText(coupon: CouponLike): string {
  return couponType(coupon) === 'discount'
    ? `${discountRate(coupon.value)} 折`
    : `¥${coupon.value.toFixed(2)}`
}