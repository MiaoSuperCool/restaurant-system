<!--右侧个人信息卡（圆形头像 + 用户名/角色 + 登出按钮）-->
<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const router = useRouter()

const roleText = computed(() => (userStore.isAdmin ? '管理员' : '普通员工'))
const avatarChar = computed(() => userStore.user?.username?.charAt(0).toUpperCase() ?? '?')

async function handleLogout() {
  await userStore.logout()
  router.push('/login')
}
</script>

<template>
  <aside class="user-card">
    <div class="profile">
      <el-avatar :size="48" class="avatar">{{ avatarChar }}</el-avatar>
      <div class="info">
        <p class="name">{{ userStore.user?.username }}</p>
        <p class="role">{{ roleText }}</p>
      </div>
    </div>
    <el-button class="logout-btn" @click="handleLogout">登出</el-button>
  </aside>
</template>

<style scoped>
.user-card {
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