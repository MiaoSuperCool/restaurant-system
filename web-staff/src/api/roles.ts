import { request } from './request'
import type { Role } from './types'

/** 角色列表接口返回的 data */
export interface RoleListData {
  roles: Role[]
}

/**
 * 角色列表（员工管理页分配角色时用）
 *
 * 只读：预置角色由后端 backend/app/rbac.py 定义、`flask seed-rbac` 落地。
 * 改权限矩阵要改那份代码，不是在界面上点。
 */
export function getRoles() {
  return request<RoleListData>({ url: '/roles', method: 'get' })
}