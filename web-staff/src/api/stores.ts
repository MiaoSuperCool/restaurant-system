import { request } from './request'
import type { Pagination, Store, StoreOption } from './types'

/** 门店列表接口返回的 data */
export interface StoreListData {
  stores: Store[]
  pagination: Pagination
}

/** 门店下拉选项接口返回的 data */
export interface StoreOptionData {
  stores: StoreOption[]
}

/** 新增/编辑门店的请求体（对应 StoreCreateSchema / StoreUpdateSchema） */
export interface StorePayload {
  code?: string
  name?: string
  store_type?: string
  address?: string
  phone?: string
  business_status?: string
  run_mode?: string
  remark?: string
}

/** 门店列表（登录即可读） */
export function getStores(params: { search?: string; page?: number }) {
  return request<StoreListData>({ url: '/stores', method: 'get', params })
}

/** 门店下拉选项（不分页，供各处表单选择归属门店） */
export function getStoreOptions() {
  return request<StoreOptionData>({ url: '/stores/options', method: 'get' })
}

/** 新增门店（管理员；code/name 必填） */
export function createStore(data: StorePayload) {
  return request<Store>({ url: '/stores', method: 'post', data })
}

/** 修改门店（管理员） */
export function updateStore(id: number, data: StorePayload) {
  return request<Store>({ url: `/stores/${id}`, method: 'put', data })
}

/** 删除门店（管理员） */
export function deleteStore(id: number) {
  return request<null>({ url: `/stores/${id}`, method: 'delete' })
}