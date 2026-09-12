import { request } from './request'
import type { Permission, Role } from './types'

/** 角色列表接口返回的 data */
export interface RoleListData {
  roles: Role[]
  /** 完整权限目录：角色矩阵页靠它渲染出所有行（含没人拥有的权限码） */
  permissions: Permission[]
}

/**
 * 角色列表 + 权限目录
 *
 * 只读：预置角色由后端 backend/app/rbac.py 定义、`flask seed-rbac` 落地。
 * 改权限矩阵要改那份代码，不是在界面上点。
 */
export function getRoles() {
  return request<RoleListData>({ url: '/roles', method: 'get' })
}