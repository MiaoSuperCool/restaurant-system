<template>
  <view class="page">
    <view class="hero">
      <text class="hero-title">门店助手</text>
      <text class="hero-sub">用员工账号登录（和网页端是同一个账号）</text>
    </view>

    <view class="form">
      <view class="field">
        <text class="label">账号</text>
        <input
          v-model="username"
          class="input"
          placeholder="如 shouyin"
          :disabled="loading"
          @confirm="handleLogin"
        />
      </view>
      <view class="field">
        <text class="label">密码</text>
        <input
          v-model="password"
          class="input"
          password
          placeholder="演示账号统一是 Demo123!"
          :disabled="loading"
          @confirm="handleLogin"
        />
      </view>

      <button class="btn" :disabled="loading" @tap="handleLogin">
        {{ loading ? '登录中…' : '登录' }}
      </button>

      <text v-if="error" class="error">{{ error }}</text>
    </view>

    <view class="tips">
      <text class="tips-title">演示账号</text>
      <text class="tips-line">shouyin 收银员 · dianzhang 店长 · fuwuyuan 服务员 · houcu 后厨</text>
      <text class="tips-line">密码统一 Demo123!</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { login } from '@/api/auth'
import { setSession } from '@/stores/auth'

const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  if (loading.value) return
  if (!username.value.trim() || !password.value) {
    error.value = '账号和密码都要填'
    return
  }

  loading.value = true
  error.value = ''
  try {
    const data = await login(username.value.trim(), password.value)
    setSession(data)
    // reLaunch 而不是 navigateTo：登录页不该留在页面栈里，
    // 否则首页按返回又会回到登录页
    uni.reLaunch({ url: '/pages/index/index' })
  } catch (e) {
    // request.ts 已经弹了 toast，这里再在表单里留一行——toast 一闪就没了，
    // 输错密码的时候人正低头看键盘
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 0 60rpx;
  box-sizing: border-box;
}

.hero {
  padding: 140rpx 0 80rpx;
}

.hero-title {
  display: block;
  font-size: 60rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.hero-sub {
  display: block;
  margin-top: 16rpx;
  font-size: 26rpx;
  color: #a0a0a0;
}

.form {
  background: #fff;
  border-radius: 20rpx;
  padding: 40rpx 32rpx;
}

.field {
  margin-bottom: 32rpx;
}

.label {
  display: block;
  font-size: 26rpx;
  color: #8a8a8a;
  margin-bottom: 12rpx;
}

.input {
  height: 88rpx;
  padding: 0 24rpx;
  background: #f7f7f7;
  border-radius: 12rpx;
  font-size: 30rpx;
}

.btn {
  margin-top: 16rpx;
  height: 88rpx;
  line-height: 88rpx;
  background: #1f1f1f;
  color: #fff;
  font-size: 30rpx;
  border-radius: 12rpx;
}

.btn[disabled] {
  background: #8a8a8a;
}

.error {
  display: block;
  margin-top: 24rpx;
  font-size: 26rpx;
  color: #c45656;
  text-align: center;
}

.tips {
  padding: 60rpx 0;
}

.tips-title {
  display: block;
  font-size: 24rpx;
  color: #a0a0a0;
  margin-bottom: 12rpx;
}

.tips-line {
  display: block;
  font-size: 24rpx;
  color: #a0a0a0;
  line-height: 1.8;
}
</style>