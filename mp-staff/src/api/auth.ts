import { request } from './request'
import type { Staff } from './types'

/** 登录返回的 data */
export interface LoginResult {
  token: string
  /** 秒数，前端拿它算什么时候该重新登录 */
  expires_in: number
  staff: Staff
  permissions: string[]
  /** store 本店 / all 全部 */
  data_scope: string
}

/** 首页接口返回的 data：当前员工 + 权限 + 今日经营 */
export interface HomeData {
  staff: Staff
  permissions: string[]
  data_scope: string
  today: {
    order_count: number
    revenue: number
    pending_count: number
  }
  staff_count: number
  store_count: number
}

/**
 * 员工登录（换 token）
 *
 * 和网页端**是同一次校验、两种凭据**：网页端拿的是 HttpOnly 的 session cookie
 * （浏览器自动带），这里拿的是 token（自己存着、每次放进请求头）。
 * 后端只多了一个 `/api/auth/token`，业务逻辑一行没多写。
 */
export function login(username: string, password: string) {
  return request<LoginResult>({
    url: '/api/auth/token',
    method: 'POST',
    data: { username, password },
  })
}

/**
 * 退出登录
 *
 * 后端会把 `token_version` +1，**这个员工手里所有旧 token 一起作废**——
 * 门店的公用平板登出时，本来就该把上一个人留下的凭据清干净。
 */
export function logout() {
  return request<null>({ url: '/api/auth/logout', method: 'POST' })
}

/**
 * 首页：当前员工 + 权限 + 今日经营
 *
 * 这个接口同时干两件事，所以进首页时调它一箭双雕：
 * **① 用最新的权限覆盖本地缓存**——网页端就是这么做的，改了角色不用重新登录；
 * **② 拿今日数据**——服务员/后厨一打开就想知道「今天多少单、还有几个没接」。
 *
 * （接口挂在 `/index` 而不是 `/api/*` 下，是项目早期的约定，
 * 后端的 vite 代理和 nginx 配置里都跟着转发了这一条。）
 */
export function getHome() {
  return request<HomeData>({ url: '/index', method: 'GET' })
}