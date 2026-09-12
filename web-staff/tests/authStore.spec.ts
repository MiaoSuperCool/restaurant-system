import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { Staff } from '@/api/types'

// vi.hoisted：把 mock 函数提升到 vi.mock 工厂可见的作用域（vitest 的 mock 提升机制）
const authApi = vi.hoisted(() => ({ login: vi.fn(), logout: vi.fn() }))
vi.mock('@/api/auth', () => authApi)
const mainApi = vi.hoisted(() => ({ getDashboard: vi.fn() }))
vi.mock('@/api/main', () => mainApi)

import { useAuthStore } from '@/stores/auth'

/** localStorage 的 key：故意写成与 stores/auth.ts 的常量一致，测试能抓住"key 改了但没同步测试"的漂移 */
const STORAGE_KEY = 'restaurant-system'

function makeStaff(isAdmin = false): Staff {
  return {
    id: isAdmin ? 1 : 2,
    username: isAdmin ? 'admin' : 'dianzhang',
    real_name: isAdmin ? '管理员' : '店长',
    email: 'user@example.com',
    mobile: '13800138000',
    store_id: isAdmin ? null : 1,
    store_name: isAdmin ? null : '解放路店',
    employment_type: 'full_time',
    employment_type_label: '全职',
    is_shared: false,
    is_active: true,
    is_admin: isAdmin,
    roles: isAdmin ? [] : [{ id: 5, code: 'store_manager', name: '店长' }],
    created_at: null,
  }
}

const EMPTY_SESSION = { staff: null, permissions: [], data_scope: 'store' }

/** 登录接口返回的结构 */
function makeLoginResult(isAdmin = false) {
  return {
    staff: makeStaff(isAdmin),
    permissions: isAdmin ? ['store:manage', 'audit:view'] : ['store:view', 'dish:price:edit'],
    data_scope: isAdmin ? 'all' : 'store',
  }
}

describe('useAuthStore', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    authApi.login.mockReset()
    authApi.logout.mockReset()
    mainApi.getDashboard.mockReset()
  })

  it('初始状态：未登录，无任何权限', () => {
    const store = useAuthStore()
    expect(store.staff).toBeNull()
    expect(store.isLoggedIn).toBe(false)
    expect(store.isAdmin).toBe(false)
    expect(store.hasPermission('store:view')).toBe(false)
  })

  it('登录成功：写入 state 并持久化到 localStorage', async () => {
    const result = makeLoginResult(false)
    authApi.login.mockResolvedValue(result)

    const store = useAuthStore()
    await store.login('dianzhang', 'Passw0rd!')

    expect(store.staff).toEqual(result.staff)
    expect(store.isLoggedIn).toBe(true)
    expect(store.data_scope).toBe('store')
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!)).toEqual(result)
  })

  it('刷新页面后从 localStorage 恢复登录态和权限', () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(makeLoginResult(false)))
    // 相当于刷新页面后首次调用 useAuthStore：state 初始化时会去读 localStorage
    const store = useAuthStore()
    expect(store.isLoggedIn).toBe(true)
    expect(store.staff?.username).toBe('dianzhang')
    expect(store.hasPermission('store:view')).toBe(true)
    expect(store.hasPermission('audit:view')).toBe(false)
  })

  it('localStorage 里是损坏 JSON 时不崩溃，按未登录处理', () => {
    localStorage.setItem(STORAGE_KEY, '{broken json')
    const store = useAuthStore()
    expect(store.isLoggedIn).toBe(false)
  })

  it('登出：接口失败也不抛错，且强制清空本地状态', async () => {
    authApi.login.mockResolvedValue(makeLoginResult(false))
    authApi.logout.mockRejectedValue(new Error('网络错误'))

    const store = useAuthStore()
    await store.login('dianzhang', 'Passw0rd!')
    await store.logout() // 不应 reject（见 stores/auth.ts 的 try/catch 设计）

    expect(store.staff).toBeNull()
    expect(store.isLoggedIn).toBe(false)
    expect(store.permissions).toEqual([])
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('超级管理员绕过权限码检查', () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...EMPTY_SESSION, staff: makeStaff(true) }))
    const store = useAuthStore()
    // 后端下发的是全量权限码；这里额外验证 is_admin 这个旁路的兜底作用
    expect(store.hasPermission('system:config')).toBe(true)
    expect(store.hasAnyPermission(['nonsense:code'])).toBe(true)
  })

  it('hasAnyPermission：任意一个命中就算有（菜单项常常对应多个权限）', async () => {
    authApi.login.mockResolvedValue(makeLoginResult(false))
    const store = useAuthStore()
    await store.login('dianzhang', 'Passw0rd!')

    expect(store.hasAnyPermission(['store:manage', 'store:view'])).toBe(true)
    expect(store.hasAnyPermission(['store:manage', 'audit:view'])).toBe(false)
  })

  it('setSession：手动设置 / 清空登录态并同步持久化', () => {
    const store = useAuthStore()
    store.setSession(makeStaff(false), ['store:view'], 'store')
    expect(store.isLoggedIn).toBe(true)
    expect(localStorage.getItem(STORAGE_KEY)).not.toBeNull()

    store.setSession(null, [], 'store')
    expect(store.isLoggedIn).toBe(false)
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('refresh：把后端最新的权限同步回来（改了角色不用重新登录）', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(makeLoginResult(false)))
    const store = useAuthStore()
    expect(store.hasPermission('audit:view')).toBe(false)

    // 老板刚给他加了权限
    mainApi.getDashboard.mockResolvedValue({
      ...makeLoginResult(false),
      permissions: ['store:view', 'dish:price:edit', 'audit:view'],
    })
    await store.refresh()

    expect(store.hasPermission('audit:view')).toBe(true)
  })

  it('refresh 失败不影响已有登录态', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(makeLoginResult(false)))
    const store = useAuthStore()

    mainApi.getDashboard.mockRejectedValue(new Error('网络错误'))
    await store.refresh() // 不应 reject

    expect(store.isLoggedIn).toBe(true)
    expect(store.hasPermission('store:view')).toBe(true)
  })

  it('refresh 在未登录时不发请求', async () => {
    const store = useAuthStore()
    await store.refresh()
    expect(mainApi.getDashboard).not.toHaveBeenCalled()
  })
})