import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { Staff } from '@/api/types'

// vi.hoisted：把 mock 函数提升到 vi.mock 工厂可见的作用域（vitest 的 mock 提升机制）
const authApi = vi.hoisted(() => ({ login: vi.fn(), logout: vi.fn() }))
vi.mock('@/api/auth', () => authApi)

import { useAuthStore } from '@/stores/auth'

/** localStorage 的 key：故意写成与 stores/auth.ts 的常量一致，测试能抓住"key 改了但没同步测试"的漂移 */
const STORAGE_KEY = 'restaurant-system'

function makeStaff(isAdmin = false): Staff {
  return {
    id: isAdmin ? 1 : 2,
    username: isAdmin ? 'admin' : 'staff',
    real_name: isAdmin ? '管理员' : '普通员工',
    email: 'user@example.com',
    mobile: '13800138000',
    store_id: null,
    store_name: null,
    employment_type: 'full_time',
    employment_type_label: '全职',
    is_shared: false,
    is_active: true,
    is_admin: isAdmin,
    created_at: null,
  }
}

describe('useAuthStore', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    authApi.login.mockReset()
    authApi.logout.mockReset()
  })

  it('初始状态：未登录，无管理员权限', () => {
    const store = useAuthStore()
    expect(store.staff).toBeNull()
    expect(store.isLoggedIn).toBe(false)
    expect(store.isAdmin).toBe(false)
  })

  it('登录成功：写入 state 并持久化到 localStorage', async () => {
    const admin = makeStaff(true)
    authApi.login.mockResolvedValue({ staff: admin })

    const store = useAuthStore()
    await store.login('admin', 'Admin123!')

    expect(store.staff).toEqual(admin)
    expect(store.isLoggedIn).toBe(true)
    expect(store.isAdmin).toBe(true)
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!)).toEqual(admin)
  })

  it('刷新页面后从 localStorage 恢复登录态', () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(makeStaff(true)))
    // 相当于刷新页面后首次调用 useAuthStore：state 初始化时会去读 localStorage
    const store = useAuthStore()
    expect(store.isLoggedIn).toBe(true)
    expect(store.isAdmin).toBe(true)
    expect(store.staff?.username).toBe('admin')
  })

  it('localStorage 里是损坏 JSON 时不崩溃，按未登录处理', () => {
    localStorage.setItem(STORAGE_KEY, '{broken json')
    const store = useAuthStore()
    expect(store.isLoggedIn).toBe(false)
  })

  it('登出：接口失败也不抛错，且强制清空本地状态', async () => {
    authApi.login.mockResolvedValue({ staff: makeStaff(false) })
    authApi.logout.mockRejectedValue(new Error('网络错误'))

    const store = useAuthStore()
    await store.login('staff', 'Staff123!')
    await store.logout() // 不应 reject（见 stores/auth.ts 的 try/catch 设计）

    expect(store.staff).toBeNull()
    expect(store.isLoggedIn).toBe(false)
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('setStaff：手动设置 / 清空员工并同步持久化', () => {
    const store = useAuthStore()
    store.setStaff(makeStaff())
    expect(store.isLoggedIn).toBe(true)
    expect(localStorage.getItem(STORAGE_KEY)).not.toBeNull()

    store.setStaff(null)
    expect(store.isLoggedIn).toBe(false)
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
  })
})