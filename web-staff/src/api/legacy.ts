import { request } from './request'
import type { LegacyMap, Pagination, Reconciliation, SyncRecord, SyncSummary } from './types'

/** 映射列表接口返回的 data */
export interface LegacyMapListData {
  maps: LegacyMap[]
  pagination: Pagination
}

/** 同步记录接口返回的 data（summary 是全量，不跟着筛选走） */
export interface SyncRecordListData {
  records: SyncRecord[]
  summary: SyncSummary
  pagination: Pagination
}

/** 对账记录接口返回的 data */
export interface ReconciliationListData {
  records: Reconciliation[]
  pagination: Pagination
}

/** 按老号查新对象的结果；没迁过时 found 是 false、target 是 null */
export interface ResolveResult {
  found: boolean
  target_type: string
  legacy_id: string
  target: Record<string, unknown> | null
}

/** ID 映射列表（sync:view） */
export function getLegacyMaps(params: {
  search?: string
  target_type?: string
  page?: number
}) {
  return request<LegacyMapListData>({ url: '/legacy/maps', method: 'get', params })
}

/**
 * 按老系统的号查新对象
 *
 * **查不到不是错误**——「这个号没迁过」是个正常的查询结果，`found` 会是 false。
 * 客服拿着老会员号来问的时候就靠它。
 */
export function resolveLegacyId(params: { legacy_id: string; target_type?: string }) {
  return request<ResolveResult>({ url: '/legacy/maps/resolve', method: 'get', params })
}

/** 手工补一条映射（迁移时漏掉的个别人） */
export function createLegacyMap(data: {
  target_type: string
  target_id: number
  legacy_id: string
  remark?: string
}) {
  return request<LegacyMap>({ url: '/legacy/maps', method: 'post', data })
}

/** 删映射——只在录错的时候用，会在审计里留一份 */
export function deleteLegacyMap(id: number) {
  return request<null>({ url: `/legacy/maps/${id}`, method: 'delete' })
}

/** 同步记录（带全量汇总） */
export function getSyncRecords(params: {
  direction?: string
  target?: string
  category?: string
  status?: string
  page?: number
}) {
  return request<SyncRecordListData>({ url: '/legacy/sync-records', method: 'get', params })
}

/** 对账记录 */
export function getReconciliations(params: {
  category?: string
  status?: string
  store_id?: number
  biz_date?: string
  page?: number
}) {
  return request<ReconciliationListData>({
    url: '/legacy/reconciliations',
    method: 'get',
    params,
  })
}

/**
 * 跑一次对账
 *
 * `category` 是 `balance`（储值，全公司，不用传门店）或 `order`（订单，**必传门店**）。
 * 同一个（日期、门店、类别）重跑会**覆盖**旧结论——对账的语义就是重新下一遍。
 */
export function runReconciliation(data: {
  category: string
  biz_date?: string
  store_id?: number
}) {
  return request<Reconciliation>({
    url: '/legacy/reconciliations/run',
    method: 'post',
    data,
  })
}