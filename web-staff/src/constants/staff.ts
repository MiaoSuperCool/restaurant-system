/**
 * 员工枚举选项（表单下拉用）
 *
 * 取值必须与 backend/app/models/staff.py 里的常量保持一致——
 * 后端 schema 用 validate.OneOf 卡这些值，传错了会返回 422。
 * 展示用的中文名不在这里查：列表数据里后端已经带了 xxx_label 字段。
 */
import type { EnumOption } from './store'

export const EMPLOYMENT_TYPE_OPTIONS: EnumOption[] = [
  { value: 'full_time', label: '全职' },
  { value: 'part_time', label: '兼职' },
]