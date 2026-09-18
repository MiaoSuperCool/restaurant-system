import { createRouter, createWebHistory } from 'vue-router'
import { MENU_COMPANY_PERMISSIONS, MENU_STORE_PERMISSIONS } from '@/constants/menu'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue') },
    {
      // 小票不进主布局：打印时侧边栏和用户卡不该出现在纸上
      path: '/receipt/:id',
      name: 'receipt',
      component: () => import('@/views/ReceiptView.vue'),
      meta: { permissions: ['order:view'] },
    },
    {
      // 主布局作为父路由：登录后的所有页面都套在它里面
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      children: [
        { path: '', name: 'home', component: () => import('@/views/HomeView.vue') },
        {
          path: 'reports',
          name: 'reports',
          component: () => import('@/views/ReportsView.vue'),
          // 店长有 report:store、老板/运营/财务有 report:all，任一即可进。
          // **看到哪几家由数据范围决定**，不由这个码决定
          meta: { permissions: ['report:store', 'report:all'] },
        },
        {
          path: 'new-order',
          name: 'new-order',
          component: () => import('@/views/NewOrderView.vue'),
          // 代客点单（order:create）：服务员、收银员、值班经理、店长都有
          meta: { permissions: ['order:create'] },
        },
        {
          path: 'orders',
          name: 'orders',
          component: () => import('@/views/OrdersView.vue'),
          // 收银员、值班经理、店长、财务都有 order:view
          meta: { permissions: ['order:view'] },
        },
        {
          path: 'groupon-vouchers',
          name: 'groupon-vouchers',
          component: () => import('@/views/GrouponVouchersView.vue'),
          // 核销记录是给对账用的：能核销的人（收银/店长）和财务都看得到
          meta: { permissions: ['coupon:verify', 'finance:view'] },
        },
        {
          path: 'coupons',
          name: 'coupons',
          component: () => import('@/views/CouponsView.vue'),
          // 券模板管理（coupon:manage）。发券是页面里单独的按钮，要 coupon:issue——
          // 能设计券的人不一定该能随便发，后端也是两个码分开的
          meta: { permissions: ['coupon:manage'] },
        },
        {
          path: 'refunds',
          name: 'refunds',
          component: () => import('@/views/RefundsView.vue'),
          // 财务、值班经理、店长、老板都能看退款
          meta: { permissions: ['refund:view'] },
        },
        {
          path: 'members',
          name: 'members',
          component: () => import('@/views/MembersView.vue'),
          // 两个码任一即可：收银员有 member:balance:view（看余额）、
          // 运营主管有 member:view（管档案）
          meta: { permissions: ['member:view', 'member:balance:view'] },
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
          meta: { permissions: MENU_COMPANY_PERMISSIONS },
        },
        {
          path: 'categories',
          name: 'categories',
          component: () => import('@/views/CategoriesView.vue'),
          meta: { permissions: MENU_COMPANY_PERMISSIONS },
        },
        {
          path: 'store-menu',
          name: 'store-menu',
          component: () => import('@/views/StoreMenuView.vue'),
          // 门店菜单是店长的入口：他有 menu:update（本店范围），
          // 但进不了公司级的菜品/分类页
          meta: { permissions: MENU_STORE_PERMISSIONS },
        },
        {
          path: 'staff',
          name: 'staff',
          component: () => import('@/views/StaffView.vue'),
          meta: { permissions: ['staff:manage', 'staff:manage:all'] },
        },
        {
          path: 'roles',
          name: 'roles',
          component: () => import('@/views/RolesView.vue'),
          meta: { permissions: ['staff:manage', 'staff:manage:all'] },
        },
        {
          path: 'legacy',
          name: 'legacy',
          component: () => import('@/views/LegacyView.vue'),
          // 对账 + 同步记录 + ID 映射，都是「新老系统共存」那一摊，一个码管住。
          // 只有财务和老板有 sync:view
          meta: { permissions: ['sync:view'] },
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