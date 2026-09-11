<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const username = ref('')
const password = ref('')
const loading = ref(false)

async function handleLogin() {
  if (!username.value.trim() || !password.value) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    await userStore.login(username.value.trim(), password.value)
    ElMessage.success('登录成功')
    router.push('/')
  } catch {
    // 错误提示（密码错误/网络错误等）已由 request.ts 拦截器统一弹出，这里不再重复
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <h1 class="login-title">管理系统模板</h1>
      <p class="login-subtitle">请登录后继续</p>

      <el-form label-position="top" @submit.prevent="handleLogin">
        <el-form-item>
          <el-input
            v-model="username"
            placeholder="用户名"
            size="large"
            autocomplete="username"
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="password"
            type="password"
            placeholder="密码"
            size="large"
            autocomplete="current-password"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-button
          type="primary"
          class="login-btn"
          size="large"
          :loading="loading"
          @click="handleLogin"
        >
          登录
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
}

.login-card {
  width: 360px;
  padding: 44px 40px 40px;
  border: 1px solid #e5e5e5;
  border-radius: 10px;
}

.login-title {
  font-size: 22px;
  font-weight: 600;
  color: #1f1f1f;
  text-align: center;
  margin-bottom: 8px;
}

.login-subtitle {
  font-size: 13px;
  color: #8a8a8a;
  text-align: center;
  margin-bottom: 32px;
}

.login-btn {
  width: 100%;
  margin-top: 4px;
}
</style>