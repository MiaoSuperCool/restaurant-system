import { request } from './request'
import type { Pagination, User } from './types'

/** 用户列表接口返回的 data */
export interface UserListData {
  users: User[]
  pagination: Pagination
}

/** 新增/编辑用户的请求体（对应 UserCreateSchema / UserUpdateSchema） */
export interface UserPayload {
  username?: string
  real_name?: string
  email?: string
  mobile?: string
  password?: string
  is_active?: boolean
  is_admin?: boolean
}

/** 用户列表（管理员） */
export function getUsers(params: { search?: string; page?: number }) {
  return request<UserListData>({ url: '/users', method: 'get', params })
}

/** 新增用户（管理员；username/realname/email/mobile/password 必填） */
export function createUser(data: UserPayload) {
  return request<User>({ url: '/users', method: 'post', data })
}

/** 修改用户（管理员） */
export function updateUser(id: number, data: UserPayload) {
  return request<User>({ url: `/users/${id}`, method: 'put', data })
}

/** 删除用户（管理员） */
export function deleteUser(id: number) {
  return request<null>({ url: `/users/${id}`, method: 'delete' })
}