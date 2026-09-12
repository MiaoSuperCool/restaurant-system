import { request } from './request'
import type { Staff } from './types'

/** 登录接口返回的 data（/index 返回同样的结构，前端刷新时用它同步权限） */
export interface LoginResult {
  staff: Staff
  /** 该员工拥有的全部权限码，前端靠它决定显示哪些菜单和按钮 */
  permissions: string[]
  /** 数据范围：store = 只能碰本店数据，all = 全部 */
  data_scope: string
}

/** 登录 */
export function login(username: string, password: string) {
  return request<LoginResult>({
    url: '/auth',
    method: 'post',
    data: { username, password },
  })
}

/** 登出（后端 auth.py 的 logout 路由目前被 login 遮蔽，需要先修，见文末说明） */
export function logout() {
  return request<null>({
    url: '/auth/logout',
    method: 'post',
  })
}