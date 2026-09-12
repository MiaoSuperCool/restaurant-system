import { request } from './request'
import type { Category, CategoryOption, Pagination } from './types'

/** 分类列表接口返回的 data */
export interface CategoryListData {
  categories: Category[]
  pagination: Pagination
}

/** 分类下拉选项接口返回的 data */
export interface CategoryOptionData {
  categories: CategoryOption[]
}

/** 新增/编辑分类的请求体（对应 CategoryCreateSchema / CategoryUpdateSchema） */
export interface CategoryPayload {
  name?: string
  icon?: string
  is_visible?: boolean
  sort_order?: number | null
  /** 适用门店；空数组 = 全公司通用 */
  store_ids?: number[]
}

/** 分类列表 */
export function getCategories(params: { search?: string; page?: number }) {
  return request<CategoryListData>({ url: '/categories', method: 'get', params })
}

/** 分类下拉选项（不分页，供菜品表单选择分类） */
export function getCategoryOptions() {
  return request<CategoryOptionData>({ url: '/categories/options', method: 'get' })
}

/** 新增分类（menu:create） */
export function createCategory(data: CategoryPayload) {
  return request<Category>({ url: '/categories', method: 'post', data })
}

/** 修改分类（menu:update） */
export function updateCategory(id: number, data: CategoryPayload) {
  return request<Category>({ url: `/categories/${id}`, method: 'put', data })
}

/** 删除分类（menu:delete） */
export function deleteCategory(id: number) {
  return request<null>({ url: `/categories/${id}`, method: 'delete' })
}