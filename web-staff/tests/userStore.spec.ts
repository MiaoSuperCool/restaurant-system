import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { User } from '@/api/types'

// vi.hoisted：把 mock 函数提升到 vi.mock 工厂可见的作用域（vitest 的 mock 提升机制）
const authApi = vi.hoisted(() => ({ login: vi.fn(), logout: vi.fn() }))
vi.mock('@/api/auth', () => authApi)

import { useUserStore } from '@/stores/user'

/** localStorage 的 key：故意写成与 stores/user.ts 的常量一致，测试能抓住"key 改了但没同步测试"的漂移 */
const USER_STORAGE_KEY = 'restaurant-system'

function makeUser(isAdmin = false): User {
  return {
    id: isAdmin ? 1 : 2,
    username: isAdmin ? 'admin' : 'staff',
    real_name: isAdmin ? '管理员' : '普通员工',
    email: 'user@example.com',
    mobile: '13800138000',
    is_active: true,
    is_admin: isAdmin,
    created_at: null,
  }
}

describe('useUserStore', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    authApi.login.mockReset()
    authApi.logout.mockReset()
  })

  it('初始状态：未登录，无管理员权限', () => {
    const store = useUserStore()
    expect(store.user).toBeNull()
    expect(store.isLoggedIn).toBe(false)
    expect(store.isAdmin).toBe(false)
  })

  it('登录成功：写入 state 并持久化到 localStorage', async () => {
    const admin = makeUser(true)
    authApi.login.mockResolvedValue({ user: admin })

    const store = useUserStore()
    await store.login('admin', 'Admin123!')

    expect(store.user).toEqual(admin)
    expect(store.isLoggedIn).toBe(true)
    expect(store.isAdmin).toBe(true)
    expect(JSON.parse(localStorage.getItem(USER_STORAGE_KEY)!)).toEqual(admin)
  })

  it('刷新页面后从 localStorage 恢复登录态', () => {
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(makeUser(true)))
    // 相当于刷新页面后首次调用 useUserStore：state 初始化时会去读 localStorage
    const store = useUserStore()
    expect(store.isLoggedIn).toBe(true)
    expect(store.isAdmin).toBe(true)
    expect(store.user?.username).toBe('admin')
  })

  it('localStorage 里是损坏 JSON 时不崩溃，按未登录处理', () => {
    localStorage.setItem(USER_STORAGE_KEY, '{broken json')
    const store = useUserStore()
    expect(store.isLoggedIn).toBe(false)
  })

  it('登出：接口失败也不抛错，且强制清空本地状态', async () => {
    authApi.login.mockResolvedValue({ user: makeUser(false) })
    authApi.logout.mockRejectedValue(new Error('网络错误'))

    const store = useUserStore()
    await store.login('staff', 'Staff123!')
    await store.logout() // 不应 reject（见 stores/user.ts 的 try/catch 设计）

    expect(store.user).toBeNull()
    expect(store.isLoggedIn).toBe(false)
    expect(localStorage.getItem(USER_STORAGE_KEY)).toBeNull()
  })

  it('setUser：手动设置 / 清空用户并同步持久化', () => {
    const store = useUserStore()
    store.setUser(makeUser())
    expect(store.isLoggedIn).toBe(true)
    expect(localStorage.getItem(USER_STORAGE_KEY)).not.toBeNull()

    store.setUser(null)
    expect(store.isLoggedIn).toBe(false)
    expect(localStorage.getItem(USER_STORAGE_KEY)).toBeNull()
  })
})