import { createRouter, createWebHistory } from 'vue-router'
import { MENU_MANAGE_PERMISSIONS } from '@/constants/menu'
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
          path: 'orders',
          name: 'orders',
          component: () => import('@/views/OrdersView.vue'),
          // 收银员、值班经理、店长、财务都有 order:view
          meta: { permissions: ['order:view'] },
        },
        {
          path: 'stores',
          name: 'stores',
          component: () => import('@/views/StoresView.vue'),
          // 权限码要和后端的 @permission_required 一致；数组 = 任一即可
          // 这里是「看得到页面」的门槛，页面内的增删改按钮另有更严的权限
          meta: { permissions: ['store:view'] },
        },
        {
          path: 'dishes',
          name: 'dishes',
          component: () => import('@/views/DishesView.vue'),
          meta: { permissions: MENU_MANAGE_PERMISSIONS },
        },
        {
          path: 'categories',
          name: 'categories',
          component: () => import('@/views/CategoriesView.vue'),
          meta: { permissions: MENU_MANAGE_PERMISSIONS },
        },
        {
          path: 'store-menu',
          name: 'store-menu',
          component: () => import('@/views/StoreMenuView.vue'),
          // 门店菜单是「菜单管理」的一部分：能改菜单的人才进得来。
          // 这也顺带保证了页面里的门店下拉可用（这几个角色都有 store:view）
          meta: { permissions: MENU_MANAGE_PERMISSIONS },
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