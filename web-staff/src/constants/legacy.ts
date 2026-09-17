/**
 * 老系统共存的枚举选项 + 颜色
 *
 * 取值必须与 backend/app/models/legacy.py 里的常量保持一致——
 * 后端 schema 用 validate.OneOf 卡这些值，传错了会返回 422。
 */
import type { EnumOption } from './store'

export const SYNC_DIRECTION_OPTIONS: EnumOption[] = [
  { value: 'push', label: '推出去' },
  { value: 'pull', label: '拉进来' },
]

export const SYNC_CATEGORY_OPTIONS: EnumOption[] = [
  { value: 'order', label: '订单' },
  { value: 'member', label: '会员' },
  { value: 'balance', label: '储值' },
]

export const SYNC_STATUS_OPTIONS: EnumOption[] = [
  { value: 'success', label: '成功' },
  { value: 'failed', label: '失败' },
  { value: 'pending', label: '待重试' },
]

/** 同步状态 → el-tag 的 type */
export const SYNC_STATUS_TAG: Record<string, string> = {
  success: 'success',
  failed: 'danger',
  pending: 'warning',
}

export const RECONCILIATION_CATEGORY_OPTIONS: EnumOption[] = [
  { value: 'order', label: '订单' },
  { value: 'balance', label: '储值' },
]

/** 对账状态 → el-tag 的 type */
export const RECONCILIATION_STATUS_TAG: Record<string, string> = {
  matched: 'success',
  mismatched: 'danger',
}

/** 映射对象类型 → 文案（后端 to_dict 里已经带了 label，这里只用于筛选下拉） */
export const MAP_TARGET_OPTIONS: EnumOption[] = [
  { value: 'member', label: '会员' },
  { value: 'balance', label: '储值账户' },
]

/**
 * 对账差异里那一条说的是谁
 *
 * 会员对账带 `member_name`、订单对账带 `order_no`，界面上不能只显示一个 id——
 * 财务拿着 id 还得再去搜一遍
 */
export function detailWho(item: {
  member_name?: string
  member_id?: number
  order_no?: string
  order_id?: number
}): string {
  return item.member_name || item.order_no || `#${item.member_id ?? item.order_id ?? ''}`
}