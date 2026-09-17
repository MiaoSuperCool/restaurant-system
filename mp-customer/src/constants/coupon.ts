/**
 * 券的文案
 *
 * 和 `web-staff/src/constants/coupon.ts` 是同一套逻辑，各端一份——
 * 两个前端是两个独立的工程，共享的是**后端的 API 契约**，不是源码。
 * （真要共享得抽一个包出来，为了这两个函数不值当。）
 *
 * **类型字段两个名字都得认**：券模板上叫 `type`，用户手里那张券上叫
 * `template_type`。只认一个的话，折扣券会被当成满减，显示成「满 ¥50 减 ¥0.85」。
 */
interface CouponLike {
  type?: string
  template_type?: string
  value: number
  min_amount: number
}

function couponType(coupon: CouponLike): string {
  return coupon.type ?? coupon.template_type ?? ''
}

/** 折扣率 → 「8.5」这种给人看的数字（0.85 → 8.5 折，不是「减 15%」） */
function discountRate(value: number): string {
  return String(Number((value * 10).toFixed(1)))
}

/**
 * 券的门槛，如「满 ¥100」「无门槛」
 *
 * **只返回门槛，不带面额**：卡片上那个大字已经写着「减 ¥20」或「8.5 折」了，
 * 再来一句「满 ¥100 减 ¥20」是重复的——小屏幕上还会折成两行。
 * （员工端有 `describeCoupon` 那种一整句的版本，那边是表格，一行放得下。）
 */
export function couponThresholdText(coupon: CouponLike): string {
  return coupon.min_amount > 0 ? `满 ¥${coupon.min_amount.toFixed(0)}` : '无门槛'
}

/** 券上那个大字：满减是金额，折扣是折扣率 */
export function couponValueText(coupon: CouponLike): string {
  return couponType(coupon) === 'discount'
    ? `${discountRate(coupon.value)} 折`
    : `¥${coupon.value.toFixed(2)}`
}