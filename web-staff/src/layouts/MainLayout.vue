<script setup lang="ts">
import { onMounted } from 'vue'
import Sidebar from '@/components/Sidebar.vue'
import StaffCard from '@/components/StaffCard.vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

// 页面刷新后从后端同步一次权限：localStorage 里存的是登录那一刻的快照，
// 老板中途改了谁的权限，不刷新的话对方要重新登录才生效
onMounted(() => {
  authStore.refresh()
})
</script>

<template>
  <div class="main-layout">
    <Sidebar />
    <main class="content">
      <router-view />
    </main>
    <StaffCard />
  </div>
</template>

<style scoped>
.main-layout {
  display: flex;
  min-height: 100vh;
  background: #fff;
}

.content {
  flex: 1;
  border-left: 1px solid #e5e5e5;
  border-right: 1px solid #e5e5e5;
  overflow-y: auto;
}
</style>