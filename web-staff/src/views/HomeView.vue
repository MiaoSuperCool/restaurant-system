<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getDashboard } from '@/api/main'
import type { DashboardData } from '@/api/main'
import { formatPrice } from '@/utils/format'

const authStore = useAuthStore()
const router = useRouter()
const dashboard = ref<DashboardData | null>(null)
const loading = ref(false)

const roleText = computed(() => {
  const staff = dashboard.value?.staff
  if (!staff) return '—'
  if (staff.is_admin) return '超级管理员'
  if (!staff.roles.length) return '未分配角色'
  return staff.roles.map((role) => role.name).join('、')
})

/** 看板上的数字都受数据范围限制——店长看到的是本店，老板看到的是全公司 */
const scopeHint = computed(() =>
  dashboard.value?.data_scope === 'all' ? '全公司' : dashboard.value?.staff?.store_name ?? '本店'
)

const cards = computed(() => {
  const today = dashboard.value?.today
  return [
    { key: 'revenue', label: '今日营业额', value: formatPrice(today?.revenue ?? 0), primary: true },
    { key: 'orders', label: '今日订单', value: String(today?.order_count ?? 0) },
    { key: 'pending', label: '待接单', value: String(today?.pending_count ?? 0), alert: (today?.pending_count ?? 0) > 0 },
  ]
})

/** 快捷入口按权限过滤：没权限的入口摆在那里点了会 403，不如不显示 */
const shortcuts = computed(() => {
  const items: { label: string; path: string; query?: Record<string, string> }[] = []
  if (authStore.hasPermission('order:create')) items.push({ label: '去点单', path: '/new-order' })
  if (authStore.hasPermission('order:view')) {
    items.push({ label: '处理订单', path: '/orders', query: { status: 'pending' } })
  }
  if (authStore.hasPermission('menu:update')) items.push({ label: '调整本店菜单', path: '/store-menu' })
  if (authStore.hasAnyPermission(['menu:create', 'menu:delete'])) {
    items.push({ label: '管理菜品', path: '/dishes' })
  }
  return items
})

async function loadDashboard() {
  loading.value = true
  try {
    dashboard.value = await getDashboard()
  } catch {
    // 错误提示由 request.ts 拦截器统一弹出
  } finally {
    loading.value = false
  }
}

onMounted(loadDashboard)
</script>

<template>
  <div class="home">
    <div class="head">
      <h1 class="welcome">Hello, {{ authStore.staff?.real_name || authStore.staff?.username }}</h1>
      <span class="scope">数据范围：{{ scopeHint }}</span>
    </div>

    <div v-loading="loading" class="home-body">
      <div class="stats-row">
        <div
          v-for="card in cards"
          :key="card.key"
          class="stat-card"
          :class="{ alert: card.alert }"
        >
          <h2>{{ card.label }}</h2>
          <p class="value" :class="{ large: card.primary }">{{ card.value }}</p>
        </div>
      </div>

      <div class="card shortcut-card">
        <h2>快捷入口</h2>
        <div class="shortcuts">
          <el-button
            v-for="item in shortcuts"
            :key="item.path"
            @click="router.push({ path: item.path, query: item.query })"
          >
            {{ item.label }}
          </el-button>
          <span v-if="shortcuts.length === 0" class="muted">当前角色没有可用的操作入口</span>
        </div>
      </div>

      <div class="card info-card">
        <h2>账号</h2>
        <div class="info-row">
          <span class="info-label">角色</span>
          <span>{{ roleText }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">归属门店</span>
          <span>{{ dashboard?.staff?.store_name ?? '总部' }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">全公司</span>
          <span>{{ dashboard?.store_count ?? 0 }} 家门店 · {{ dashboard?.staff_count ?? 0 }} 名员工</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.home {
  padding: 32px;
}

.head {
  display: flex;
  align-items: baseline;
  gap: 16px;
  margin-bottom: 24px;
}

.welcome {
  font-size: 24px;
  font-weight: 600;
  color: #1f1f1f;
}

.scope {
  font-size: 13px;
  color: #8a8a8a;
}

.stats-row {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
}

.stat-card {
  flex: 1;
  border: 1px solid #e5e5e5;
  border-radius: 10px;
  padding: 20px;
  background: #fff;
}

/* 待接单不是 0 的时候标红：首页就该一眼看出「有活要干」 */
.stat-card.alert {
  border-color: #c45656;
  background: #fdf6f6;
}

.stat-card.alert h2 {
  color: #c45656;
}

.stat-card h2 {
  font-size: 13px;
  font-weight: 500;
  color: #8a8a8a;
  margin-bottom: 12px;
}

.stat-card .value {
  font-size: 26px;
  font-weight: 600;
  color: #1f1f1f;
}

.stat-card .value.large {
  font-size: 32px;
}

.card {
  border: 1px solid #e5e5e5;
  border-radius: 10px;
  padding: 20px;
  background: #fff;
  margin-bottom: 20px;
}

.card h2 {
  font-size: 13px;
  font-weight: 500;
  color: #8a8a8a;
  margin-bottom: 14px;
}

.shortcuts {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.info-row {
  display: flex;
  gap: 16px;
  font-size: 14px;
  color: #1f1f1f;
  padding: 6px 0;
}

.info-label {
  width: 72px;
  color: #8a8a8a;
}

.muted {
  font-size: 13px;
  color: #a0a0a0;
}
</style>
