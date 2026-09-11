import { request } from './request'
import type { Pagination, Staff } from './types'

/** 员工列表接口返回的 data */
export interface StaffListData {
  staff: Staff[]
  pagination: Pagination
}

/** 新增/编辑员工的请求体（对应 StaffCreateSchema / StaffUpdateSchema） */
export interface StaffPayload {
  username?: string
  real_name?: string
  email?: string
  mobile?: string
  password?: string
  /** 归属门店；总部账号传 null */
  store_id?: number | null
  employment_type?: string
  is_shared?: boolean
  is_active?: boolean
  is_admin?: boolean
}

/** 员工列表（管理员） */
export function getStaffList(params: { search?: string; page?: number }) {
  return request<StaffListData>({ url: '/staff', method: 'get', params })
}

/** 新增员工（管理员；username/real_name/email/mobile/password 必填） */
export function createStaff(data: StaffPayload) {
  return request<Staff>({ url: '/staff', method: 'post', data })
}

/** 修改员工（管理员） */
export function updateStaff(id: number, data: StaffPayload) {
  return request<Staff>({ url: `/staff/${id}`, method: 'put', data })
}

/** 删除员工（管理员） */
export function deleteStaff(id: number) {
  return request<null>({ url: `/staff/${id}`, method: 'delete' })
}