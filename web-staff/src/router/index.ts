import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue') },
    {
      // 主布局作为父路由：登录后的所有页面都套在它里面
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      children: [
        { path: '', name: 'home', component: () => import('@/views/HomeView.vue') },
        {
          path: 'stores',
          name: 'stores',
          component: () => import('@/views/StoresView.vue'),
          // 权限码要和后端的 @permission_required 一致；数组 = 任一即可
          // 这里是「看得到页面」的门槛，页面内的增删改按钮另有更严的权限
          meta: { permissions: ['store:view'] },
        },
        {
          path: 'staff',
          name: 'staff',
          component: () => import('@/views/StaffView.vue'),
          meta: { permissions: ['staff:manage', 'staff:manage:all'] },
        },
        {
          path: 'audit',
          name: 'audit',
          component: () => import('@/views/AuditView.vue'),
          meta: { permissions: ['audit:view'] },
        },
        // 新业务页面在这里加子路由，并在 meta.permissions 里声明需要的权限码
      ],
    },
    // 未知路径统一回首页，避免点还没建的菜单时白屏
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to) => {
  const authStore = useAuthStore()
  if (!authStore.isLoggedIn && to.name !== 'login') {
    return { name: 'login' }
  }
  if (authStore.isLoggedIn && to.name === 'login') {
    return { name: 'home' }
  }
  // 路由级权限守卫：没权限的话直接输 URL 也进不去
  // （后端接口同样有 @permission_required 兜底，前端只是体验层）
  const required = to.meta.permissions as string[] | undefined
  if (required?.length && !authStore.hasAnyPermission(required)) {
    return { name: 'home' }
  }
})

export default router