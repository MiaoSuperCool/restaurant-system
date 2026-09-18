<!-- 左侧导航（按权限渲染菜单 + 点击高亮）-->
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { MENU_COMPANY_PERMISSIONS, MENU_STORE_PERMISSIONS } from '@/constants/menu'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

/**
 * 全部菜单项，每项声明自己需要哪些权限码（数组 = 任一即可，空数组 = 登录就能看）
 *
 * 加新页面时在这里补一项，权限码要和后端的 @permission_required 对得上。
 */
const ALL_MENUS = [
  { name: '主页面', path: '/', permissions: [] as string[] },
  // 报表紧跟主页面：都是「看数」的入口，而且店长/老板一上来就是看这个
  { name: '报表', path: '/reports', permissions: ['report:store', 'report:all'] },
  // 点单和订单放前面：收银员一天到晚开着的就是这两页
  { name: '点单', path: '/new-order', permissions: ['order:create'] },
  { name: '订单', path: '/orders', permissions: ['order:view'] },
  { name: '退款', path: '/refunds', permissions: ['refund:view'] },
  { name: '团购券', path: '/groupon-vouchers', permissions: ['coupon:verify', 'finance:view'] },
  // 本店自己发的券（券模板 + 发券）——和上面的「团购券」不是一回事：
  // 那个是美团/抖音买来的券核销，这个是自家会员券包里的券
  { name: '优惠券', path: '/coupons', permissions: ['coupon:manage'] },
  // 会员：两个码任一即可。收银员有 member:balance:view（要告诉顾客还能抵多少）、
  // 运营主管有 member:view——看余额的前提是先找到这个人，谁都不该被挡在门外
  { name: '会员', path: '/members', permissions: ['member:view', 'member:balance:view'] },
  { name: '门店', path: '/stores', permissions: ['store:view'] },
  { name: '菜品', path: '/dishes', permissions: MENU_COMPANY_PERMISSIONS },
  { name: '分类', path: '/categories', permissions: MENU_COMPANY_PERMISSIONS },
  { name: '门店菜单', path: '/store-menu', permissions: MENU_STORE_PERMISSIONS },
  // 排班放在员工上面：都是「管人」的事，而且排班天天要用，员工资料很少动
  { name: '排班', path: '/schedule', permissions: ['schedule:view'] },
  { name: '员工', path: '/staff', permissions: ['staff:manage', 'staff:manage:all'] },
  // 角色矩阵放在员工旁边：给人分配角色的时候要知道这个角色能干什么
  { name: '角色', path: '/roles', permissions: ['staff:manage', 'staff:manage:all'] },
  // 对账放在审计旁边：都是「事后回看」的入口，看的也都是同一批人（财务/老板）
  { name: '对账', path: '/legacy', permissions: ['sync:view'] },
  { name: '审计日志', path: '/audit', permissions: ['audit:view'] },
]

const menus = computed(() =>
  ALL_MENUS.filter(
    (item) => item.permissions.length === 0 || authStore.hasAnyPermission(item.permissions)
  )
)

function isActive(path: string): boolean {
  return route.path === path
}
</script>

<template>
  <nav class="sidebar">
    <div class="logo">管理系统</div>
    <ul class="menu">
      <li
        v-for="item in menus"
        :key="item.path"
        class="menu-item"
        :class="{ active: isActive(item.path) }"
        @click="router.push(item.path)"
      >
        {{ item.name }}
      </li>
    </ul>
  </nav>
</template>

<style scoped>
.sidebar {
  width: 200px;
  flex-shrink: 0;
  padding: 16px 12px;
}

.logo {
  font-size: 18px;
  font-weight: 600;
  padding: 8px 12px 20px;
  color: #1f1f1f;
}

.menu {
  list-style: none;
}

.menu-item {
  padding: 12px 16px;
  margin-bottom: 4px;
  border-radius: 8px;
  font-size: 14px;
  color: #1f1f1f;
  cursor: pointer;
  transition: background 0.15s;
}

.menu-item:hover {
  background: #f2f2f2;
}

/* 当前页面高亮：黑底白字，对应构象里"被点击的按钮会有颜色变化" */
.menu-item.active {
  background: #1f1f1f;
  color: #fff;
}
</style>