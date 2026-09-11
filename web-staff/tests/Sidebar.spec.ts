import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { User } from '@/api/types'
import Sidebar from '@/components/Sidebar.vue'
import { useUserStore } from '@/stores/user'

function makeUser(isAdmin: boolean): User {
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

/** Sidebar 内部用到 useRoute/useRouter，挂载时需要真实的 router 实例 */
function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div />' } }],
  })
}

describe('Sidebar 菜单按角色渲染', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('普通用户只看到"主页面"', async () => {
    const router = makeRouter()
    useUserStore().user = makeUser(false)

    const wrapper = mount(Sidebar, { global: { plugins: [router] } })
    await router.isReady()

    expect(wrapper.findAll('.menu-item').map((item) => item.text())).toEqual(['主页面'])
  })

  it('管理员额外看到"门店"、"用户"和"审计日志"', async () => {
    const router = makeRouter()
    useUserStore().user = makeUser(true)

    const wrapper = mount(Sidebar, { global: { plugins: [router] } })
    await router.isReady()

    expect(wrapper.findAll('.menu-item').map((item) => item.text())).toEqual([
      '主页面',
      '门店',
      '用户',
      '审计日志',
    ])
  })
})