<template>
  <view class="page">
    <!-- 没登录：不拦着，只是把「登录能多什么」说清楚 -->
    <view v-if="!loggedIn" class="guest">
      <text class="guest-title">还没登录</text>
      <text class="guest-sub">
        不登录也能点单——只是想看余额、积分和券的话，用手机号登一下
      </text>
      <view class="guest-btn" @tap="goLogin">手机号登录 / 注册</view>
    </view>

    <template v-else>
      <view class="me">
        <view class="me-main">
          <text class="me-name">{{ displayName() }}</text>
          <text class="me-mobile">{{ account?.mobile }}</text>
        </view>
        <text class="logout" @tap="handleLogout">退出</text>
      </view>

      <view class="assets">
        <view class="asset">
          <text class="asset-value">{{ formatPrice(account?.balance.total ?? 0) }}</text>
          <text class="asset-label">储值余额</text>
        </view>
        <view class="asset">
          <text class="asset-value">{{ account?.points.balance ?? 0 }}</text>
          <text class="asset-label">积分（抵 {{ formatPrice(account?.points.amount ?? 0) }}）</text>
        </view>
        <view class="asset">
          <text class="asset-value">{{ usableCount }}</text>
          <text class="asset-label">可用券</text>
        </view>
      </view>

      <view class="entries">
        <view class="entry" @tap="go('/pages/coupons/coupons')">
          <text class="entry-title">券中心</text>
          <text class="entry-sub">看看有什么能领的</text>
        </view>
        <view class="entry" @tap="go('/pages/coupons/coupons?tab=mine')">
          <text class="entry-title">我的券包</text>
          <text class="entry-sub">{{ couponSummary }}</text>
        </view>
        <view class="entry" @tap="goOrders">
          <text class="entry-title">我的订单</text>
          <text class="entry-sub">下单记录和状态</text>
        </view>
      </view>

      <text class="footnote">
        储值是充进账户的钱（本金能退、赠送不退）；积分是消费攒的，100 分抵 1 元。
        券分「可用 / 已用 / 已过期 / 未生效」四档，过期的不会再出现在可用里。
      </text>
    </template>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getMyAccount, getMyCoupons } from '@/api/member'
import type { MyAccount } from '@/api/member'
import { clearSession, displayName, isLoggedIn } from '@/stores/memberAuth'
import { formatPrice } from '@/utils/format'

const account = ref<MyAccount | null>(null)
const loggedIn = ref(false)
const usableCount = ref(0)
const couponSummary = ref('还没领过券')

/**
 * **onShow 不是 onMounted**：从券中心领完券回来，这里得跟着变
 * （领了券，「可用券」那个数字不变的话，会让人以为没领上）
 */
async function load() {
  loggedIn.value = isLoggedIn()
  if (!loggedIn.value) {
    account.value = null
    return
  }

  try {
    account.value = await getMyAccount()
  } catch {
    // token 过期/被停用：request.ts 已经把本地的清掉了，这里退回未登录状态
    loggedIn.value = isLoggedIn()
  }

  try {
    // 券包的汇总单独拉一次——「可用券」只看 unused 那档，
    // 过期的和还没生效的不该混进这个数（它们本来就「现在用不了」）
    const usable = await getMyCoupons({ status: 'unused' })
    usableCount.value = usable.pagination.total

    const all = await getMyCoupons({})
    couponSummary.value = all.pagination.total
      ? `一共 ${all.pagination.total} 张，可用 ${usable.pagination.total} 张`
      : '还没领过券'
  } catch {
    // 上面那次失败已经处理过了
  }
}

function go(url: string) {
  uni.navigateTo({ url })
}

/** 订单页是底部 tab 之一，**只能 switchTab**（navigateTo 打不开 tab 页） */
function goOrders() {
  uni.switchTab({ url: '/pages/orders/orders' })
}

function goLogin() {
  uni.navigateTo({ url: '/pages/login/login' })
}

function handleLogout() {
  // **顾客端没有「服务端登出」**：token 是无状态的，服务端没存它。
  // 把手机上的删掉就是这个账号在这台设备上登出了
  // （员工端不一样，那边要踢掉公用平板上别人的凭据，见 AuthService.logout）
  uni.showModal({
    title: '退出登录',
    content: '退出后要看余额和券得重新登录。',
    success: (res) => {
      if (!res.confirm) return
      clearSession()
      load()
    },
  })
}

onShow(load)
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 32rpx;
  box-sizing: border-box;
}

.guest {
  margin-top: 120rpx;
  padding: 60rpx 40rpx;
  background: #fff;
  border-radius: 20rpx;
}

.guest-title {
  display: block;
  font-size: 40rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.guest-sub {
  display: block;
  margin-top: 20rpx;
  font-size: 26rpx;
  color: #a0a0a0;
  line-height: 1.8;
}

.guest-btn {
  margin-top: 48rpx;
  height: 88rpx;
  line-height: 88rpx;
  text-align: center;
  background: #1f1f1f;
  color: #fff;
  font-size: 30rpx;
  border-radius: 12rpx;
}

.me {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 36rpx 32rpx;
  background: #fff;
  border-radius: 20rpx;
}

.me-name {
  display: block;
  font-size: 38rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.me-mobile {
  display: block;
  margin-top: 8rpx;
  font-size: 26rpx;
  color: #a0a0a0;
}

.logout {
  padding: 12rpx 8rpx;
  font-size: 28rpx;
  color: #8a8a8a;
}

.assets {
  display: flex;
  margin-top: 24rpx;
  padding: 36rpx 0;
  background: #fff;
  border-radius: 20rpx;
}

.asset {
  flex: 1;
  text-align: center;
}

.asset-value {
  display: block;
  font-size: 40rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.asset-label {
  display: block;
  margin-top: 10rpx;
  font-size: 22rpx;
  color: #a0a0a0;
}

.entries {
  margin-top: 24rpx;
}

.entry {
  padding: 32rpx;
  margin-bottom: 20rpx;
  background: #fff;
  border-radius: 20rpx;
}

.entry:active {
  background: #f0f0f0;
}

.entry-title {
  display: block;
  font-size: 32rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.entry-sub {
  display: block;
  margin-top: 10rpx;
  font-size: 24rpx;
  color: #a0a0a0;
}

.footnote {
  display: block;
  margin-top: 32rpx;
  padding: 0 8rpx 60rpx;
  font-size: 24rpx;
  color: #b0b0b0;
  line-height: 1.9;
}
</style>