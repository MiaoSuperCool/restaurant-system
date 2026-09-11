<!-- 左侧导航（按角色渲染菜单 + 点击高亮）-->
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

/** 菜单项：所有角色都有主页面；门店/员工/审计日志仅管理员可见 */
const menus = computed(() => {
  const base = [{ name: '主页面', path: '/' }]
  if (authStore.isAdmin) {
    base.push(
      { name: '门店', path: '/stores' },
      { name: '员工', path: '/staff' },
      { name: '审计日志', path: '/audit' }
    )
  }
  return base
})

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