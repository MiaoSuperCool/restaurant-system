/**
 * 登录态：token + 当前员工 + 权限
 *
 * **没有用 Pinia**——和后端一致，这个端只有「一个人、一份权限」，
 * 一个模块级的 `reactive` 就够了。顾客端（mp-customer）也是这么做的，
 * 理由写在那边：多一个依赖换不来什么。
 *
 * token 存在本地存储里（`uni.setStorageSync`），关掉小程序再打开还在——
 * 后端的有效期给了一周（`MP_TOKEN_MAX_AGE`），服务员不用每天上班先登一次。
 */
import { reactive } from 'vue'
import { TOKEN_KEY } from '@/api/request'
import type { Staff } from '@/api/types'

interface AuthState {
  staff: Staff | null
  permissions: string[]
  data_scope: string
}

export const authState = reactive<AuthState>({
  staff: null,
  permissions: [],
  data_scope: '',
})

export function getToken(): string {
  return uni.getStorageSync(TOKEN_KEY) || ''
}

export function setSession(data: {
  token?: string
  staff: Staff
  permissions: string[]
  data_scope: string
}) {
  if (data.token) uni.setStorageSync(TOKEN_KEY, data.token)
  authState.staff = data.staff
  authState.permissions = data.permissions
  authState.data_scope = data.data_scope
}

export function clearSession() {
  uni.removeStorageSync(TOKEN_KEY)
  authState.staff = null
  authState.permissions = []
  authState.data_scope = ''
}

/**
 * 有没有某个权限码
 *
 * **这只是体验层**：决定「按钮要不要显示」。后端每个接口都会重新判权，
 * 前端就算把这里的返回值改了也拿不到数据。
 */
export function hasPermission(code: string): boolean {
  return authState.staff?.is_admin === true || authState.permissions.includes(code)
}

/** 任一即可（和后端的 `@permission_required(a, b)` 一个语义） */
export function hasAnyPermission(...codes: string[]): boolean {
  return codes.some(hasPermission)
}

/** 当前账号归属的门店。总部账号（运营/财务/老板）没有归属门店，是 null */
export function myStoreId(): number | null {
  return authState.staff?.store_id ?? null
}