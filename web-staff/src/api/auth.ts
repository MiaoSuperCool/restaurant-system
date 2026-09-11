import { request } from './request'
import type { Staff } from './types'

/** 登录接口返回的 data */
export interface LoginResult {
  staff: Staff
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