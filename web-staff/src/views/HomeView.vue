<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { getDashboard } from '@/api/main'
import type { DashboardData } from '@/api/main'

const authStore = useAuthStore()
const dashboard = ref<DashboardData | null>(null)
const loading = ref(false)

const roleText = computed(() => {
  const staff = dashboard.value?.staff
  if (!staff) return '—'
  if (staff.is_admin) return '超级管理员'
  if (!staff.roles.length) return '未分配角色'
  return staff.roles.map((role) => role.name).join('、')
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
    <h1 class="welcome">Hello, {{ authStore.staff?.real_name || authStore.staff?.username }}</h1>

    <div v-loading="loading" class="home-body">
      <div class="stats-row">
        <div class="card stat-card">
          <h2>当前角色</h2>
          <p class="value">{{ roleText }}</p>
        </div>
        <div class="card stat-card">
          <h2>门店总数</h2>
          <p class="value">{{ dashboard?.store_count ?? 0 }}</p>
        </div>
        <div class="card stat-card">
          <h2>员工总数</h2>
          <p class="value">{{ dashboard?.staff_count ?? 0 }}</p>
        </div>
      </div>

      <!-- 模板占位：新项目的首页统计/看板写在这里 -->
      <div class="card placeholder">
        <h2>从这里开始你的业务</h2>
        <p>这是模板首页。新项目请在 api/main.ts 定义你的首页数据结构，并在后端 main.py 的 index() 里返回对应的业务统计。</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.home {
  padding: 32px;
}

.welcome {
  font-size: 24px;
  font-weight: 600;
  color: #1f1f1f;
  margin-bottom: 24px;
}

.stats-row {
  display: flex;
  gap: 24px;
  margin-bottom: 24px;
}

.card {
  border: 1px solid #e5e5e5;
  border-radius: 10px;
  padding: 20px;
  background: #fff;
}

.card h2 {
  font-size: 14px;
  font-weight: 500;
  color: #8a8a8a;
  margin-bottom: 16px;
}

.stat-card {
  width: 240px;
}

.stat-card .value {
  font-size: 28px;
  font-weight: 600;
  color: #1f1f1f;
}

.placeholder p {
  font-size: 14px;
  color: #666;
  line-height: 1.8;
}
</style>