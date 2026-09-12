/**
 * 退款相关枚举选项
 *
 * 取值必须与 backend/app/models/refund.py 的常量保持一致。
 */
import type { EnumOption } from './store'

export const REFUND_STATUS_OPTIONS: EnumOption[] = [
  { value: 'pending', label: '待审批' },
  { value: 'approved', label: '已批准（待打款）' },
  { value: 'rejected', label: '已驳回' },
  { value: 'settled', label: '已退款' },
]

export const REFUND_TYPE_OPTIONS: EnumOption[] = [
  { value: 'online', label: '线上退款' },
  { value: 'offline', label: '线下补录' },
]

export const REFUND_METHOD_OPTIONS: EnumOption[] = [
  { value: 'original', label: '原路退回' },
  { value: 'cash', label: '现金' },
  { value: 'balance', label: '退到储值' },
]

/** 退款状态 → el-tag 的 type。待审批用 danger，让审批人一眼看到要处理的单子 */
export const REFUND_STATUS_TAG: Record<string, string> = {
  pending: 'danger',
  approved: 'warning',
  rejected: 'info',
  settled: 'success',
}
