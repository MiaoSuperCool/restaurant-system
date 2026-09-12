/**
 * 团购券相关枚举选项
 *
 * 取值必须与 backend/app/models/groupon_voucher.py 的常量保持一致。
 */
import type { EnumOption } from './store'

export const GROUPON_PLATFORM_OPTIONS: EnumOption[] = [
  { value: 'meituan', label: '美团' },
  { value: 'douyin', label: '抖音' },
  { value: 'other', label: '其他' },
]
