import { request } from './request'
import type { StoreMenuRow } from './types'

/**
 * 某门店的菜单（menu:view）
 *
 * 返回的每一行是「菜品基础 + 本店覆盖」合并后的结果：`price` 是本店实际售价、
 * `is_available` 是本店是否上架。**服务员点单必须看这一份**，
 * 不能看公司级的基础菜单——那样会点到本店已经下架的菜，
 * 也会报错一个本店根本不卖的价格。
 */
export function getStoreMenu(storeId: number) {
  return request<{ dishes: StoreMenuRow[] }>({
    url: `/api/stores/${storeId}/menu`,
    method: 'GET',
  })
}