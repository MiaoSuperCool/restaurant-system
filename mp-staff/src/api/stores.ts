import { request } from './request'
import type { StoreOption } from './types'

/**
 * 门店下拉选项（`store:view`）
 *
 * **受数据范围限制**：店长只会看到自己那家，总部账号（运营/财务/老板）看到全部。
 * 所以「能不能选门店」等价于「有没有 `store:view`」——
 * 服务员/收银员没有这个码，他们只有自己那一家，不用选。
 */
export function getStoreOptions() {
  return request<{ stores: StoreOption[] }>({ url: '/api/stores/options', method: 'GET' })
}