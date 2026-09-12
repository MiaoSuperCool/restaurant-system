<!-- 左侧导航（按权限渲染菜单 + 点击高亮）-->
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { MENU_MANAGE_PERMISSIONS } from '@/constants/menu'
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
  // 订单放前面：收银员一天到晚都开着这一页
  { name: '订单', path: '/orders', permissions: ['order:view'] },
  { name: '门店', path: '/stores', permissions: ['store:view'] },
  { name: '菜品', path: '/dishes', permissions: MENU_MANAGE_PERMISSIONS },
  { name: '分类', path: '/categories', permissions: MENU_MANAGE_PERMISSIONS },
  { name: '门店菜单', path: '/store-menu', permissions: MENU_MANAGE_PERMISSIONS },
  { name: '员工', path: '/staff', permissions: ['staff:manage', 'staff:manage:all'] },
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