<template>
  <view class="page">
    <view v-if="!loggedIn" class="guest">
      <text class="guest-title">登录后能领券</text>
      <text class="guest-sub">券是挂在账号上的，得先认出来你是谁</text>
      <view class="guest-btn" @tap="goLogin">手机号登录 / 注册</view>
    </view>

    <template v-else>
      <view class="tabs">
        <text
          class="tab"
          :class="{ active: tab === 'center' }"
          @tap="switchTab('center')"
        >
          券中心
        </text>
        <text
          class="tab"
          :class="{ active: tab === 'mine' }"
          @tap="switchTab('mine')"
        >
          我的券包
        </text>
      </view>

      <!-- ---------- 券中心 ---------- -->
      <template v-if="tab === 'center'">
        <view v-if="loading" class="hint">加载中…</view>
        <view v-else-if="center.length === 0" class="hint">
          <text>现在没有能领的券</text>
          <text class="hint-sub">店里做活动的时候会放到这儿</text>
        </view>

        <view v-else class="cards">
          <view v-for="item in center" :key="item.id" class="coupon">
            <view class="coupon-left">
              <text class="coupon-value">{{ couponValueText(item) }}</text>
              <text class="coupon-cond">{{ couponThresholdText(item) }}</text>
            </view>
            <view class="coupon-right">
              <text class="coupon-name">{{ item.name }}</text>
              <text class="coupon-validity">{{ validityText(item) }}</text>
              <!-- 领不到时把原因写出来：**一张券摆在眼前却说不清为什么领不了，
                   比它干脆不出现更让人恼火** -->
              <view v-if="item.can_claim" class="claim-btn" @tap="handleClaim(item)">
                领取
              </view>
              <text v-else class="blocked">{{ item.blocked_reason }}</text>
            </view>
          </view>
        </view>
      </template>

      <!-- ---------- 我的券包 ---------- -->
      <template v-else>
        <view class="filters">
          <text
            v-for="item in FILTERS"
            :key="item.value"
            class="filter"
            :class="{ active: filter === item.value }"
            @tap="switchFilter(item.value)"
          >
            {{ item.label }}
          </text>
        </view>

        <view v-if="loading" class="hint">加载中…</view>
        <view v-else-if="mine.length === 0" class="hint">
          <text>这一档没有券</text>
          <text class="hint-sub">去券中心看看有什么能领的</text>
        </view>

        <view v-else class="cards">
          <view v-for="item in mine" :key="item.id" class="coupon">
            <view class="coupon-left" :class="{ dim: item.status !== 'unused' }">
              <text class="coupon-value">{{ couponValueText(item) }}</text>
              <text class="coupon-cond">{{ couponThresholdText(item) }}</text>
            </view>
            <view class="coupon-right">
              <text class="coupon-name">{{ item.template_name }}</text>
              <text class="coupon-validity">
                {{ item.valid_to ? `有效期至 ${formatTime(item.valid_to)}` : '长期有效' }}
              </text>
            </view>
            <text class="coupon-status" :class="item.status">{{ item.status_label }}</text>
          </view>
        </view>

        <text class="footnote">
          「可用」里只放现在真能用上的券——过期的、还没到生效时间的都不混进来。
          到店报手机号，收银员那边也能看到你这些券。
        </text>
      </template>
    </template>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { claimCoupon, getCouponCenter, getMyCoupons } from '@/api/member'
import type { ClaimableCoupon, MemberCoupon } from '@/api/types'
import { couponThresholdText, couponValueText } from '@/constants/coupon'
import { isLoggedIn } from '@/stores/memberAuth'
import { formatTime } from '@/utils/format'

const FILTERS = [
  { value: 'unused', label: '可用' },
  { value: 'used', label: '已用' },
  { value: 'expired', label: '已过期' },
  { value: 'not_started', label: '未生效' },
]

const tab = ref<'center' | 'mine'>('center')
const filter = ref('unused')
const center = ref<ClaimableCoupon[]>([])
const mine = ref<MemberCoupon[]>([])
const loading = ref(false)
const loggedIn = ref(false)

async function loadCenter() {
  loading.value = true
  try {
    center.value = (await getCouponCenter()).coupons
  } catch {
    // request.ts 已经弹了提示
  } finally {
    loading.value = false
  }
}

async function loadMine() {
  loading.value = true
  try {
    mine.value = (await getMyCoupons({ status: filter.value })).coupons
  } catch {
    // 同上
  } finally {
    loading.value = false
  }
}

function load() {
  loggedIn.value = isLoggedIn()
  if (!loggedIn.value) return
  if (tab.value === 'center') {
    loadCenter()
  } else {
    loadMine()
  }
}

function switchTab(value: 'center' | 'mine') {
  if (tab.value === value) return
  tab.value = value
  load()
}

function switchFilter(value: string) {
  if (filter.value === value) return
  filter.value = value
  loadMine()
}

/** 「领完即止」「每人限领 2 张」这类信息放在券名下面，领之前就知道 */
function validityText(item: ClaimableCoupon): string {
  const parts: string[] = []
  if (item.valid_to) parts.push(`${formatTime(item.valid_to)} 前有效`)
  if (item.total_quantity) parts.push(`已领 ${item.issued_count}/${item.total_quantity}`)
  if (!item.is_all_stores) parts.push(item.store_names.join('、'))
  return parts.join(' · ') || '长期有效'
}

async function handleClaim(item: ClaimableCoupon) {
  try {
    await claimCoupon(item.id)
    uni.showToast({ title: '领取成功', icon: 'success' })
    // 每次领完都重新拉：份数、每人限领的剩余都会变
    loadCenter()
  } catch {
    // 领不到的原因后端说得很具体，request.ts 已经弹出来了
  }
}

function goLogin() {
  uni.navigateTo({ url: '/pages/login/login' })
}

// 从「我的」那页可以带 ?tab=mine 直接落在券包上
onLoad((options) => {
  if (options && options.tab === 'mine') tab.value = 'mine'
})

// 登录页返回之后要能刷出来——所以用 onShow 而不是 onLoad
onShow(load)
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 24rpx;
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

.tabs {
  display: flex;
  padding: 8rpx 0 24rpx;
}

.tab {
  padding: 12rpx 32rpx;
  margin-right: 16rpx;
  border-radius: 32rpx;
  font-size: 28rpx;
  color: #1f1f1f;
  background: #fff;
}

.tab.active {
  background: #1f1f1f;
  color: #fff;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  padding-bottom: 20rpx;
}

.filter {
  padding: 8rpx 24rpx;
  margin: 0 12rpx 12rpx 0;
  border-radius: 32rpx;
  font-size: 24rpx;
  color: #666;
  background: #fff;
}

.filter.active {
  color: #1f1f1f;
  font-weight: 600;
}

.cards {
  padding-bottom: 40rpx;
}

.coupon {
  display: flex;
  align-items: center;
  padding: 32rpx;
  margin-bottom: 20rpx;
  background: #fff;
  border-radius: 20rpx;
}

.coupon-left {
  width: 180rpx;
  flex-shrink: 0;
  text-align: center;
}

.coupon-left.dim {
  opacity: 0.45;
}

.coupon-value {
  display: block;
  font-size: 44rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.coupon-cond {
  display: block;
  margin-top: 6rpx;
  font-size: 22rpx;
  color: #a0a0a0;
}

.coupon-right {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.coupon-name {
  font-size: 30rpx;
  color: #1f1f1f;
}

.coupon-validity {
  margin-top: 10rpx;
  font-size: 22rpx;
  color: #a0a0a0;
}

.claim-btn {
  margin-top: 16rpx;
  padding: 8rpx 36rpx;
  background: #1f1f1f;
  color: #fff;
  font-size: 26rpx;
  border-radius: 32rpx;
}

.blocked {
  margin-top: 16rpx;
  font-size: 24rpx;
  color: #c45656;
}

.coupon-status {
  flex-shrink: 0;
  margin-left: 16rpx;
  font-size: 24rpx;
  color: #8a8a8a;
}

.coupon-status.used,
.coupon-status.expired {
  color: #b0b0b0;
}

.coupon-status.not_started {
  color: #d48806;
}

.hint {
  padding: 120rpx 0;
  text-align: center;
  font-size: 26rpx;
  color: #a0a0a0;
}

.hint-sub {
  display: block;
  margin-top: 12rpx;
  font-size: 24rpx;
  color: #b0b0b0;
}

.footnote {
  display: block;
  padding: 8rpx 12rpx 60rpx;
  font-size: 24rpx;
  color: #b0b0b0;
  line-height: 1.9;
}
</style>