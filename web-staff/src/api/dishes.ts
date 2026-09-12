import { request } from './request'
import type { Dish, Pagination } from './types'

/** 菜品列表接口返回的 data */
export interface DishListData {
  dishes: Dish[]
  pagination: Pagination
}

/**
 * 规格选项的提交形态
 *
 * 和读回来的 DishOption 的区别：id 是可选的——新加的选项还没 id，
 * 已存在的选项必须把 id 带上，后端靠它认出「这是原来那个」而不是新建一个。
 */
export interface DishOptionPayload {
  id?: number
  name: string
  extra_price: number
  sort_order?: number
}

/** 规格组的提交形态；id 语义同上。数组顺序就是显示顺序 */
export interface DishOptionGroupPayload {
  id?: number
  name: string
  selection_type: string
  is_required: boolean
  sort_order?: number
  options: DishOptionPayload[]
}

/** 新增/编辑菜品的请求体（对应 DishCreateSchema / DishUpdateSchema） */
export interface DishPayload {
  category_id?: number
  name?: string
  image?: string
  description?: string
  base_price?: number
  status?: string
  sort_order?: number | null
  /** 传了就整体对齐更新规格结构，不传表示不动 */
  option_groups?: DishOptionGroupPayload[]
}

/** 菜品列表（可按分类筛选） */
export function getDishes(params: { search?: string; page?: number; category_id?: number }) {
  return request<DishListData>({ url: '/dishes', method: 'get', params })
}

/** 菜品详情（含规格组与选项，编辑表单回填用） */
export function getDish(id: number) {
  return request<Dish>({ url: `/dishes/${id}`, method: 'get' })
}

/** 新增菜品（menu:create；菜品基础是全公司数据，还需要「全部」数据范围） */
export function createDish(data: DishPayload) {
  return request<Dish>({ url: '/dishes', method: 'post', data })
}

/** 修改菜品（menu:update；改价另需 dish:price:edit，改状态另需 dish:online） */
export function updateDish(id: number, data: DishPayload) {
  return request<Dish>({ url: `/dishes/${id}`, method: 'put', data })
}

/** 删除菜品（menu:delete；已被门店菜单或订单引用时会失败，改用「已停售」） */
export function deleteDish(id: number) {
  return request<null>({ url: `/dishes/${id}`, method: 'delete' })
}