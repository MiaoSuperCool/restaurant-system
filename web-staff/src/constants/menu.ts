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
 * 「公司级菜单管理」（菜品 / 分类）的准入权限，任一即可
 *
 * 两个细节：
 *
 * 1. 没用 menu:view：收银员和服务员也有 menu:view（点单要看菜单），
 *    但他们不该在侧边栏看到菜单管理。
 *
 * 2. 也没用 menu:update：店长有 menu:update，但菜品和分类是**全公司数据**，
 *    他改不了（后端按数据范围拦住）。菜单只按 menu:update 放行的话，
 *    店长会看到一个点进去什么都动不了的页面——能进但一操作就 403，体验很糟。
 *    店长该走的入口是「门店菜单」。
 */
export const MENU_COMPANY_PERMISSIONS = ['menu:create', 'menu:delete']

/** 「门店菜单」（本店价格/上下架/限量）的准入权限 */
export const MENU_STORE_PERMISSIONS = ['menu:update']

/** 菜品状态 → el-tag 的 type */
export const DISH_STATUS_TAG: Record<string, string> = {
  active: 'success',
  discontinued: 'info',
}