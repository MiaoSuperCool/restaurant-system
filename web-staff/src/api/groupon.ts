import { request } from './request'
import type { GrouponVoucher, Order, Pagination } from './types'

/** 核销记录列表接口返回的 data */
export interface GrouponListData {
  vouchers: GrouponVoucher[]
  pagination: Pagination
}

/** 核销接口返回的 data */
export interface GrouponVerifyResult {
  voucher: GrouponVoucher
  order: Order
}

/** 核销请求体（对应 GrouponVerifySchema） */
export interface GrouponVerifyPayload {
  code: string
  amount: number
  platform?: string
}

/**
 * 核销团购券（coupon:verify）
 *
 * 会做两件事：记核销记录（对账用）+ 记一笔团购券收款。
 * **同一张券码不能核销两次**——重复核销会被后端拒掉。
 */
export function verifyGroupon(orderId: number, data: GrouponVerifyPayload) {
  return request<GrouponVerifyResult>({
    url: `/orders/${orderId}/vouchers`,
    method: 'post',
    data,
  })
}

/** 核销记录列表（受数据范围限制；财务对账用） */
export function getGrouponVouchers(params: { search?: string; page?: number }) {
  return request<GrouponListData>({ url: '/groupon-vouchers', method: 'get', params })
}
