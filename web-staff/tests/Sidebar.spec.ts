import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { Staff } from '@/api/types'
import Sidebar from '@/components/Sidebar.vue'
import { useAuthStore } from '@/stores/auth'

function makeStaff(isAdmin = false): Staff {
  return {
    id: isAdmin ? 1 : 2,
    username: isAdmin ? 'laoban' : 'dianzhang',
    real_name: isAdmin ? '老板' : '店长',
    email: 'user@example.com',
    mobile: '13800138000',
    store_id: null,
    store_name: null,
    employment_type: 'full_time',
    employment_type_label: '全职',
    is_shared: false,
    is_active: true,
    is_admin: isAdmin,
    roles: [],
    created_at: null,
  }
}

/** 模拟一次登录：写入员工和权限 */
function loginAs(isAdmin: boolean, permissions: string[]) {
  useAuthStore().setSession(makeStaff(isAdmin), permissions, isAdmin ? 'all' : 'store')
}

/** Sidebar 内部用到 useRoute/useRouter，挂载时需要真实的 router 实例 */
function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div />' } }],
  })
}

async function menuTexts() {
  const router = makeRouter()
  const wrapper = mount(Sidebar, { global: { plugins: [router] } })
  await router.isReady()
  return wrapper.findAll('.menu-item').map((item) => item.text())
}

describe('Sidebar 菜单按权限渲染', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('没有任何权限的员工只看到"主页面"', async () => {
    loginAs(false, [])
    expect(await menuTexts()).toEqual(['主页面'])
  })

  it('后厨只有 order:view，看到"主页面"和"订单"', async () => {
    loginAs(false, ['menu:view', 'order:view'])
    expect(await menuTexts()).toEqual(['主页面', '订单'])
  })

  it('店长看到除审计外的全部菜单', async () => {
    // 店长的权限：store:view + order:view + menu:update + dish:* + staff:manage
    loginAs(false, ['store:view', 'order:view', 'menu:update', 'dish:price:edit', 'staff:manage'])
    expect(await menuTexts()).toEqual([
      '主页面',
      '订单',
      '门店',
      '菜品',
      '分类',
      '门店菜单',
      '员工',
    ])
  })

  it('收银员看得到订单，看不到菜单管理和员工管理', async () => {
    // menu:view 只是「看菜单」（点单要用），不是「管菜单」
    loginAs(false, ['menu:view', 'order:create', 'order:view', 'pay:collect'])
    expect(await menuTexts()).toEqual(['主页面', '订单'])
  })

  it('老板看到全部菜单', async () => {
    loginAs(true, [])
    expect(await menuTexts()).toEqual([
      '主页面',
      '订单',
      '门店',
      '菜品',
      '分类',
      '门店菜单',
      '员工',
      '审计日志',
    ])
  })

  it('运营主管有 store:view 和菜单管理，但没有员工管理和审计', async () => {
    loginAs(false, ['store:view', 'menu:create', 'campaign:manage'])
    expect(await menuTexts()).toEqual(['主页面', '门店', '菜品', '分类', '门店菜单'])
  })
})
