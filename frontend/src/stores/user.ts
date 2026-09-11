import { defineStore } from 'pinia'
import { login as loginApi, logout as logoutApi } from '@/api/auth'
import type { User } from '@/api/types'

/** 用户信息在 localStorage 里的 key（新项目可改成自己的前缀，避免多站点冲突） */
const USER_STORAGE_KEY = 'vue3-template-user'

/** 从 localStorage 恢复用户（刷新页面不丢登录态） */
function loadUser(): User | null {
  try {
    return JSON.parse(localStorage.getItem(USER_STORAGE_KEY) || 'null')
  } catch {
    return null
  }
}

/** 写入/清除 localStorage */
function saveUser(user: User | null) {
  if (user) {
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user))
  } else {
    localStorage.removeItem(USER_STORAGE_KEY)
  }
}

export const useUserStore = defineStore('user', {
  state: () => ({
    /** 当前登录用户；初始化时从 localStorage 恢复 */
    user: loadUser(),
  }),

  getters: {
    /** 是否管理员：Sidebar 菜单、路由守卫都用它 */
    isAdmin: (state) => state.user?.is_admin ?? false,
    /** 是否已登录 */
    isLoggedIn: (state) => state.user !== null,
  },

  actions: {
    /** 登录：调接口 → 存 state → 持久化 */
    async login(username: string, password: string) {
      const { user } = await loginApi(username, password)
      this.user = user
      saveUser(user)
      return user
    },

    /** 登出：调接口 + 清空本地状态（接口失败也强制清，保证 UI 一定退出） */
    async logout() {
      try {
        await logoutApi()
      } catch {
        // 接口失败（网络问题等）不阻断本地登出：吞掉错误，下方 finally 照常清空
      } finally {
        this.user = null
        saveUser(null)
      }
    },

    /** 手动设置用户（以后若接 /api/auth/me 恢复会话会用到） */
    setUser(user: User | null) {
      this.user = user
      saveUser(user)
    },
  },
})