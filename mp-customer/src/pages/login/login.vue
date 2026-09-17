<template>
  <view class="page">
    <view class="hero">
      <text class="hero-title">登录会员</text>
      <text class="hero-sub">用手机号登录，看余额、积分和券</text>
    </view>

    <view class="form">
      <view class="field">
        <text class="label">手机号</text>
        <input
          v-model="mobile"
          class="input"
          type="number"
          :maxlength="11"
          placeholder="11 位手机号"
          :disabled="sending"
        />
      </view>

      <view class="field">
        <text class="label">验证码</text>
        <view class="code-row">
          <input
            v-model="code"
            class="input code-input"
            type="number"
            :maxlength="6"
            placeholder="6 位数字"
          />
          <view
            class="code-btn"
            :class="{ disabled: !canSend }"
            @tap="handleSend"
          >
            {{ countdown > 0 ? `${countdown} 秒后重发` : '获取验证码' }}
          </view>
        </view>
      </view>

      <button class="btn" :disabled="loggingIn" @tap="handleLogin">
        {{ loggingIn ? '登录中…' : '登录 / 注册' }}
      </button>

      <text v-if="error" class="error">{{ error }}</text>
    </view>

    <view class="tips">
      <text class="tips-line">没注册过？直接登就行——第一次登录就是注册。</text>
      <text class="tips-line">这个店不强制登录，不登录也能点单。</text>
      <text v-if="demoCode" class="tips-demo">
        演示环境验证码直接显示：{{ demoCode }}（真实环境会发短信）
      </text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onUnload } from '@dcloudio/uni-app'
import { loginWithCode, sendCode } from '@/api/member'
import { setSession } from '@/stores/memberAuth'

const mobile = ref('')
const code = ref('')
const sending = ref(false)
const loggingIn = ref(false)
const error = ref('')
const countdown = ref(0)
const demoCode = ref('')
let timer: ReturnType<typeof setInterval> | null = null

const canSend = computed(() => countdown.value === 0 && !sending.value && mobile.value.length === 11)

function tick() {
  countdown.value -= 1
  if (countdown.value <= 0 && timer) {
    clearInterval(timer)
    timer = null
  }
}

async function handleSend() {
  if (!canSend.value) return
  sending.value = true
  error.value = ''
  try {
    const data = await sendCode(mobile.value)
    // 演示环境后端会把码回显回来，直接填上——省得去翻后端日志
    if (data.code) {
      code.value = data.code
      demoCode.value = data.code
    }
    countdown.value = 60
    timer = setInterval(tick, 1000)
    uni.showToast({ title: '验证码已发送', icon: 'none' })
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    sending.value = false
  }
}

async function handleLogin() {
  if (loggingIn.value) return
  if (mobile.value.length !== 11) {
    error.value = '手机号是 11 位'
    return
  }
  if (!code.value) {
    error.value = '先获取验证码'
    return
  }

  loggingIn.value = true
  error.value = ''
  try {
    const data = await loginWithCode(mobile.value, code.value)
    setSession(data)

    if (data.is_new) {
      uni.showToast({ title: '欢迎加入', icon: 'success' })
    }
    // navigateBack 而不是 reLaunch：登录页是从「我的」点进来的，
    // 登完回到原来那一页最自然。没有上一页时才 reLaunch
    const pages = getCurrentPages()
    if (pages.length > 1) {
      uni.navigateBack()
    } else {
      uni.reLaunch({ url: '/pages/index/index' })
    }
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loggingIn.value = false
  }
}

onUnload(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 0 60rpx;
  box-sizing: border-box;
}

.hero {
  padding: 120rpx 0 60rpx;
}

.hero-title {
  display: block;
  font-size: 56rpx;
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

.code-row {
  display: flex;
  align-items: center;
}

.code-input {
  flex: 1;
}

.code-btn {
  flex-shrink: 0;
  margin-left: 16rpx;
  padding: 0 24rpx;
  height: 88rpx;
  line-height: 88rpx;
  border-radius: 12rpx;
  background: #1f1f1f;
  color: #fff;
  font-size: 26rpx;
}

.code-btn.disabled {
  background: #c8c8c8;
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
  padding: 48rpx 0;
}

.tips-line {
  display: block;
  font-size: 24rpx;
  color: #a0a0a0;
  line-height: 1.9;
}

.tips-demo {
  display: block;
  margin-top: 16rpx;
  font-size: 24rpx;
  color: #d48806;
  line-height: 1.9;
}
</style>