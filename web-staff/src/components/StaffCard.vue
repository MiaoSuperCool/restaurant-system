<!--右侧个人信息卡（圆形头像 + 姓名/角色 + 登出按钮）-->
<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const router = useRouter()

/** 角色文案：门店员工显示门店名，总部账号显示「总部」 */
const roleText = computed(() => {
  if (!authStore.staff) return ''
  if (authStore.isAdmin) return '超级管理员'
  return authStore.staff.store_name ?? '总部'
})

const displayName = computed(
  () => authStore.staff?.real_name || authStore.staff?.username || ''
)
const avatarChar = computed(() => displayName.value.charAt(0).toUpperCase() || '?')

async function handleLogout() {
  await authStore.logout()
  router.push('/login')
}
</script>

<template>
  <aside class="staff-card">
    <div class="profile">
      <el-avatar :size="48" class="avatar">{{ avatarChar }}</el-avatar>
      <div class="info">
        <p class="name">{{ displayName }}</p>
        <p class="role">{{ roleText }}</p>
      </div>
    </div>
    <el-button class="logout-btn" @click="handleLogout">登出</el-button>
  </aside>
</template>

<style scoped>
.staff-card {
  width: 240px;
  flex-shrink: 0;
  padding: 16px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.profile {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border: 1px solid #e5e5e5;
  border-radius: 10px;
}

.avatar {
  background: #1f1f1f;
  color: #fff;
}

.name {
  font-size: 14px;
  font-weight: 600;
  color: #1f1f1f;
}

.role {
  font-size: 12px;
  color: #8a8a8a;
  margin-top: 2px;
}

.logout-btn {
  width: 100%;
}
</style>