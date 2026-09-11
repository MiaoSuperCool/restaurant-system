import { request } from './request'
import type { AuditLog, Pagination } from './types'

/** 审计日志列表接口返回的 data */
export interface AuditListData {
  logs: AuditLog[]
  pagination: Pagination
}

/** 审计日志列表（管理员） */
export function getAuditLogs(params: { search?: string; page?: number }) {
  return request<AuditListData>({ url: '/audit', method: 'get', params })
}

/** 审计日志详情（管理员） */
export function getAuditLog(id: number) {
  return request<AuditLog>({ url: `/audit/${id}`, method: 'get' })
}