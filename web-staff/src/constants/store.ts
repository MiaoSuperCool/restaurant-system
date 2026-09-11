/**
 * 门店枚举选项（表单下拉用）
 *
 * 取值必须与 backend/app/models/store.py 里的常量保持一致——
 * 后端 schema 用 validate.OneOf 卡这些值，传错了会返回 422。
 * 展示用的中文名不在这里查：列表数据里后端已经带了 xxx_label 字段。
 */
export interface EnumOption {
  value: string
  label: string
}

export const STORE_TYPE_OPTIONS: EnumOption[] = [
  { value: 'fast_food', label: '快餐店' },
  { value: 'dine_in', label: '堂食大店' },
]

export const BUSINESS_STATUS_OPTIONS: EnumOption[] = [
  { value: 'open', label: '营业中' },
  { value: 'resting', label: '休息中' },
  { value: 'closed', label: '已停业' },
]

export const RUN_MODE_OPTIONS: EnumOption[] = [
  { value: 'legacy', label: '老系统' },
  { value: 'new', label: '新系统' },
]

/** 营业状态 → el-tag 的 type（列表里用颜色区分状态） */
export const BUSINESS_STATUS_TAG: Record<string, string> = {
  open: 'success',
  resting: 'warning',
  closed: 'info',
}