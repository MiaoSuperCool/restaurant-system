<script setup lang="ts">
import Sidebar from '@/components/Sidebar.vue'
import StaffCard from '@/components/StaffCard.vue'
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