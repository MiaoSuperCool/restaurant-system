import { defineStore } from 'pinia'
import { login as loginApi, logout as logoutApi } from '@/api/auth'
import type { Staff } from '@/api/types'

/**
 * 登录态（当前登录的员工）
 *
 * 叫 auth 而不是 user：这个 store 管的是"谁登录着"，
 * 而员工/顾客是两套账号体系（顾客走小程序 token，不进这里）。
 */
const STORAGE_KEY = 'restaurant-system'

/** 从 localStorage 恢复（刷新页面不丢登录态） */
function loadStaff(): Staff | null {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null')
  } catch {
    return null
  }
}

/** 写入/清除 localStorage */
function saveStaff(staff: Staff | null) {
  if (staff) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(staff))
  } else {
    localStorage.removeItem(STORAGE_KEY)
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    /** 当前登录员工；初始化时从 localStorage 恢复 */
    staff: loadStaff(),
  }),

  getters: {
    /** 超级管理员：Sidebar 菜单、路由守卫都用它 */
    isAdmin: (state) => state.staff?.is_admin ?? false,
    /** 是否已登录 */
    isLoggedIn: (state) => state.staff !== null,
  },

  actions: {
    /** 登录：调接口 → 存 state → 持久化 */
    async login(username: string, password: string) {
      const { staff } = await loginApi(username, password)
      this.staff = staff
      saveStaff(staff)
      return staff
    },

    /** 登出：调接口 + 清空本地状态（接口失败也强制清，保证 UI 一定退出） */
    async logout() {
      try {
        await logoutApi()
      } catch {
        // 接口失败（网络问题等）不阻断本地登出：吞掉错误，下方 finally 照常清空
      } finally {
        this.staff = null
        saveStaff(null)
      }
    },

    /** 手动设置当前员工（以后若接 /api/auth/me 恢复会话会用到） */
    setStaff(staff: Staff | null) {
      this.staff = staff
      saveStaff(staff)
    },
  },
})