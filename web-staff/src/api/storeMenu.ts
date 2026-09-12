import { request } from './request'
import type { StoreDish, StoreMenuRow } from './types'

/** 门店菜单接口返回的 data（不分页，一家店的菜单要一次看全） */
export interface StoreMenuData {
  dishes: StoreMenuRow[]
}

/**
 * 门店覆盖设置的请求体
 *
 * 三个字段都可选，语义是「只改传了的」：
 * - 不传 price   = 别动价格
 * - price: null  = 取消本店覆盖、改回菜品基础价
 * 这两个的区别靠「字段在不在」区分，所以千万别传 undefined 之外的占位值。
 */
export interface StoreDishPayload {
  price?: number | null
  is_available?: boolean
  daily_limit?: number | null
}

/** 某门店的菜单（菜品基础 + 本店覆盖） */
export function getStoreMenu(storeId: number, params?: { category_id?: number; search?: string }) {
  return request<StoreMenuData>({
    url: `/stores/${storeId}/menu`,
    method: 'get',
    params,
  })
}

/** 设置本店对某道菜的覆盖（没有记录就建一条） */
export function setStoreDish(storeId: number, dishId: number, data: StoreDishPayload) {
  return request<StoreDish | null>({
    url: `/stores/${storeId}/dishes/${dishId}`,
    method: 'put',
    data,
  })
}

/** 清除本店覆盖，恢复成「用基础价、可售、不限量」 */
export function resetStoreDish(storeId: number, dishId: number) {
  return request<null>({
    url: `/stores/${storeId}/dishes/${dishId}`,
    method: 'delete',
  })
}