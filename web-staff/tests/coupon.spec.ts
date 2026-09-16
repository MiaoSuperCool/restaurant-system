import { describe, expect, it } from 'vitest'
import { couponValueText, describeCoupon } from '@/constants/coupon'

describe('券的文案', () => {
  it('满减券说「满 ¥100 减 ¥20」', () => {
    expect(describeCoupon({ type: 'full_cut', value: 20, min_amount: 100 })).toBe(
      '满 ¥100 减 ¥20.00'
    )
  })

  it('折扣券说「打 8.5 折」——0.85 是折扣率不是「减 0.85」', () => {
    expect(describeCoupon({ type: 'discount', value: 0.85, min_amount: 50 })).toBe(
      '满 ¥50 打 8.5 折'
    )
  })

  it('券模板叫 type、用户持券叫 template_type，两个都得认', () => {
    // 只认一个名字的话，顾客券包里的折扣券会显示成「满 ¥50 减 ¥0.85」
    expect(describeCoupon({ template_type: 'discount', value: 0.85, min_amount: 50 })).toBe(
      '满 ¥50 打 8.5 折'
    )
  })

  it('没门槛就写「无门槛」', () => {
    expect(describeCoupon({ type: 'full_cut', value: 10, min_amount: 0 })).toBe('无门槛 减 ¥10.00')
  })

  it('整折不留小数点：0.9 是「9 折」不是「9.0 折」', () => {
    expect(couponValueText({ type: 'discount', value: 0.9 })).toBe('9 折')
    expect(couponValueText({ type: 'full_cut', value: 20 })).toBe('¥20.00')
  })
})