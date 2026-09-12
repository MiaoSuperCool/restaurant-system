/**
 * 菜单相关枚举选项（表单下拉用）
 *
 * 取值必须与 backend/app/models/ 下的常量保持一致——
 * 后端 schema 用 validate.OneOf 卡这些值，传错了会返回 422。
 * 展示用的中文名不在这里查：列表数据里后端已经带了 xxx_label 字段。
 */
import type { EnumOption } from './store'

export const DISH_STATUS_OPTIONS: EnumOption[] = [
  { value: 'active', label: '在售' },
  { value: 'discontinued', label: '已停售' },
]

export const SELECTION_TYPE_OPTIONS: EnumOption[] = [
  { value: 'single', label: '单选' },
  { value: 'multiple', label: '多选' },
]

/**
 * 「菜单管理」页面组（菜品 / 分类）的准入权限，任一即可
 *
 * 没用 menu:view：收银员和服务员也有 menu:view（点单要看菜单），
 * 但他们不该在侧边栏看到菜单管理。这里要的是「能改菜单的人」。
 */
export const MENU_MANAGE_PERMISSIONS = ['menu:create', 'menu:update', 'menu:delete']

/** 菜品状态 → el-tag 的 type */
export const DISH_STATUS_TAG: Record<string, string> = {
  active: 'success',
  discontinued: 'info',
}