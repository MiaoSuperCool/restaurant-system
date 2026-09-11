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
          // 门店增删改暂按管理员卡（权限码体系落地后换成 store:manage）
          meta: { requiresAdmin: true },
        },
        {
          path: 'staff',
          name: 'staff',
          component: () => import('@/views/StaffView.vue'),
          meta: { requiresAdmin: true },
          //meta的作用是给这个路由打上一个标记，说明访问它需要管理员身份，导航守卫就可以可以检测到 requiresAdmin 标记，执行权限校验
        },
        {
          path: 'audit',
          name: 'audit',
          component: () => import('@/views/AuditView.vue'),
          meta: { requiresAdmin: true },
        },
        // 新业务页面在这里加子路由；仅管理员可见的页面加 meta: { requiresAdmin: true }
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
  // 路由级角色守卫：非管理员直接输 URL 也进不了管理页面
  // （后端接口同样有 admin_required 兜底，前端只是体验层）
  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    return { name: 'home' }
  }
})

export default router