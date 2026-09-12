import { defineStore } from 'pinia'
import { login as loginApi, logout as logoutApi } from '@/api/auth'
import { getDashboard } from '@/api/main'
import type { Staff } from '@/api/types'

/**
 * 登录态（当前登录的员工 + 他的权限）
 *
 * 叫 auth 而不是 user：这个 store 管的是「谁登录着、他能干什么」，
 * 而员工/顾客是两套账号体系（顾客走小程序 token，不进这里）。
 */
const STORAGE_KEY = 'restaurant-system'

interface Session {
  staff: Staff | null
  permissions: string[]
  data_scope: string
}

/** 从 localStorage 恢复（刷新页面不丢登录态和权限） */
function loadSession(): Session {
  const empty: Session = { staff: null, permissions: [], data_scope: 'store' }
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null')
    if (!raw?.staff) return empty
    return {
      staff: raw.staff,
      permissions: raw.permissions ?? [],
      data_scope: raw.data_scope ?? 'store',
    }
  } catch {
    return empty
  }
}

/** 写入/清除 localStorage */
function saveSession(session: Session) {
  if (session.staff) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
  } else {
    localStorage.removeItem(STORAGE_KEY)
  }
}

export const useAuthStore = defineStore('auth', {
  state: (): Session => loadSession(),

  getters: {
    /** 超级管理员：绕过所有权限码检查（见后端 staff.py 的 has_permission） */
    isAdmin: (state) => state.staff?.is_admin ?? false,
    /** 是否已登录 */
    isLoggedIn: (state) => state.staff !== null,

    /**
     * 有没有某个权限码
     *
     * 注意：这纯粹是体验层——决定菜单显不显示、按钮渲不渲染。
     * 真正的权限边界在后端每个接口上，前端就算改了这里的值也拿不到数据。
     */
    hasPermission: (state) => {
      return (code: string) => {
        if (!state.staff) return false
        if (state.staff.is_admin) return true
        return state.permissions.includes(code)
      }
    },

    /** 有没有其中任意一个权限码（菜单项常常对应多个权限） */
    hasAnyPermission: (state) => {
      return (codes: string[]) => {
        if (!state.staff) return false
        if (state.staff.is_admin) return true
        return codes.some((code) => state.permissions.includes(code))
      }
    },
  },

  actions: {
    /** 登录：调接口 → 存 state → 持久化 */
    async login(username: string, password: string) {
      const data = await loginApi(username, password)
      this.setSession(data.staff, data.permissions, data.data_scope)
      return data.staff
    },

    /** 登出：调接口 + 清空本地状态（接口失败也强制清，保证 UI 一定退出） */
    async logout() {
      try {
        await logoutApi()
      } catch {
        // 接口失败（网络问题等）不阻断本地登出：吞掉错误，下方 finally 照常清空
      } finally {
        this.setSession(null, [], 'store')
      }
    },

    /**
     * 刷新权限：页面刷新后调一次 /index，把最新的角色/权限同步回来。
     *
     * 不这么做的话，老板给某个店长加了权限，对方得重新登录才生效
     * （localStorage 里存的是登录那一刻的权限快照）。
     */
    async refresh() {
      if (!this.isLoggedIn) return
      try {
        const data = await getDashboard()
        this.setSession(data.staff, data.permissions, data.data_scope)
      } catch {
        // 刷新失败不影响已有登录态：可能是网络抖动，也可能 401 由拦截器处理
      }
    },

    /** 手动设置登录态（登录和刷新共用；清空传 null） */
    setSession(staff: Staff | null, permissions: string[], dataScope: string) {
      this.staff = staff
      this.permissions = permissions
      this.data_scope = dataScope
      saveSession({ staff, permissions, data_scope: dataScope })
    },
  },
})