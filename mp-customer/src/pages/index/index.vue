<template>
  <view class="page">
    <!-- ---------- 门店卡片 ---------- -->
    <view class="store">
      <view class="store-head">
        <view class="store-title">
          <text class="store-name">{{ storeState.current?.name || '还没选门店' }}</text>
          <text v-if="storeState.current" class="store-type">{{ storeState.current.store_type_label }}</text>
        </view>
        <text class="switch" @tap="openPicker">{{ storeState.current ? '切换 ›' : '选择 ›' }}</text>
      </view>

      <template v-if="storeState.current">
        <text v-if="storeState.current.description" class="store-desc">{{ storeState.current.description }}</text>
        <text class="store-address">{{ storeState.current.address }}</text>
        <view class="store-meta">
          <text v-if="storeState.current.business_hours">营业时间 {{ storeState.current.business_hours }}</text>
          <text class="phone" @tap="callStore">{{ storeState.current.phone }}</text>
        </view>
      </template>

      <text v-else class="store-empty">
        选一家门店，才能看菜单和下单
      </text>
    </view>

    <!-- ---------- 近期活动 ---------- -->
    <view class="section">
      <view class="section-head">
        <text class="section-title">近期活动</text>
        <text v-if="activities.length" class="section-more" @tap="goCoupons">
          全部 ›
        </text>
      </view>

      <view v-if="loadingActivities" class="hint">加载中…</view>

      <view v-else-if="activities.length === 0" class="hint">
        <text>最近没有活动</text>
        <text class="hint-sub">有活动的时候会出现在这儿</text>
      </view>

      <view v-else class="activities">
        <view v-for="item in activities" :key="item.id" class="activity">
          <view class="activity-left">
            <text class="activity-value">{{ couponValueText(item) }}</text>
            <text class="activity-cond">{{ couponThresholdText(item) }}</text>
          </view>
          <view class="activity-right">
            <text class="activity-name">{{ item.name }}</text>
            <text class="activity-sub">{{ activitySub(item) }}</text>
          </view>
          <view
            class="activity-btn"
            :class="{ done: !item.can_claim }"
            @tap="handleClaim(item)"
          >
            {{ item.can_claim ? '领取' : '已领' }}
          </view>
        </view>
      </view>
    </view>

    <!-- ---------- 去点餐 ---------- -->
    <view class="cta" :class="{ disabled: !storeState.current }" @tap="goMenu">
      {{ storeState.current ? `去 ${storeState.current.name} 点餐` : '先选一家门店' }}
    </view>

    <text class="footnote">
      选好门店之后，「点餐」那个 tab 里就是这家店的菜单。
      换门店在这儿切——每家店的菜单和价格可能不一样。
    </text>

    <!-- ---------- 门店选择弹层 ---------- -->
    <view v-if="pickerVisible" class="mask" @tap="pickerVisible = false">
      <view class="sheet" @tap.stop>
        <view class="sheet-head">
          <text class="sheet-title">选择门店</text>
          <text class="sheet-close" @tap="pickerVisible = false">×</text>
        </view>

        <scroll-view class="sheet-body" scroll-y>
          <view
            v-for="item in stores"
            :key="item.id"
            class="store-option"
            :class="{ active: item.id === storeState.current?.id }"
            @tap="chooseStore(item)"
          >
            <view class="option-main">
              <text class="option-name">{{ item.name }}</text>
              <text class="option-address">{{ item.address }}</text>
              <text v-if="item.business_hours" class="option-hours">
                营业 {{ item.business_hours }}
              </text>
            </view>
            <text v-if="item.id === storeState.current?.id" class="option-check">✓</text>
          </view>
        </scroll-view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getStores } from '@/api/public'
import { claimCoupon, getCouponCenter } from '@/api/member'
import type { ClaimableCoupon, StoreBrief } from '@/api/types'
import { couponThresholdText, couponValueText } from '@/constants/coupon'
import { isLoggedIn } from '@/stores/memberAuth'
import { loadCurrentStore, setCurrentStore, storeState } from '@/stores/currentStore'

const stores = ref<StoreBrief[]>([])
const activities = ref<ClaimableCoupon[]>([])
const loadingActivities = ref(false)
const pickerVisible = ref(false)

/** 首页只露前两条：想看全部去券中心，别把首页堆成一屏券 */
const MAX_ACTIVITIES = 2

async function loadStores() {
  try {
    stores.value = (await getStores()).stores
    // 一家店都没选过（第一次进来）时，默认选第一家——
    // 让顾客先看到东西，比让他先做一道选择题好。选错了随时能切
    if (!loadCurrentStore() && stores.value.length) {
      setCurrentStore(stores.value[0])
    }
  } catch {
    // request.ts 已经弹了提示
  }
}

async function loadActivities() {
  loadingActivities.value = true
  try {
    // **这个接口不用登录**：顾客端不强制登录，首页一进来就是登录墙太难看。
    // 不登录时后端按「一张都没领过」算，点「领取」的时候才要求登录
    const data = await getCouponCenter()
    activities.value = data.coupons
      .filter((item) => item.can_claim)
      .slice(0, MAX_ACTIVITIES)
  } catch {
    // 同上
  } finally {
    loadingActivities.value = false
  }
}

/** 卡片第二行：有效期 + 「已领 x/y」这类信息 */
function activitySub(item: ClaimableCoupon): string {
  const parts: string[] = []
  if (item.valid_to) parts.push(`${item.valid_to.slice(5, 10)} 前有效`)
  if (item.total_quantity) parts.push(`已领 ${item.issued_count}/${item.total_quantity}`)
  if (!item.is_all_stores) parts.push(item.store_names.join('、'))
  return parts.join(' · ') || '长期有效'
}

function openPicker() {
  pickerVisible.value = true
}

function chooseStore(item: StoreBrief) {
  setCurrentStore(item)
  pickerVisible.value = false
  uni.showToast({ title: `已切到${item.name}`, icon: 'none' })
}

function callStore() {
  if (!storeState.current?.phone) return
  uni.makePhoneCall({ phoneNumber: storeState.current.phone })
}

function goMenu() {
  if (!storeState.current) {
    pickerVisible.value = true
    return
  }
  // tab 页面必须用 switchTab，navigateTo 会失败
  uni.switchTab({ url: '/pages/menu/menu' })
}

function goCoupons() {
  uni.navigateTo({ url: '/pages/coupons/coupons' })
}

async function handleClaim(item: ClaimableCoupon) {
  if (!isLoggedIn()) {
    uni.showModal({
      title: '登录后领券',
      content: '券是挂在账号上的，用手机号登一下就能领',
      confirmText: '去登录',
      success: (res) => {
        if (res.confirm) uni.navigateTo({ url: '/pages/login/login' })
      },
    })
    return
  }

  try {
    await claimCoupon(item.id)
    uni.showToast({ title: '领取成功', icon: 'success' })
    loadActivities()
  } catch {
    // 领不到的原因后端说得很具体，request.ts 已经弹出来了
  }
}

/**
 * 每次进首页都刷一遍活动——**用 onShow 不用 onMounted**：
 * 从券中心领完券回来，首页的「已领 x/y」得跟着变；门店也可能刚被切过
 */
onShow(() => {
  loadStores()
  loadActivities()
})
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 24rpx;
  box-sizing: border-box;
}

/* ---------- 门店卡片 ---------- */
.store {
  padding: 36rpx 32rpx;
  background: #fff;
  border-radius: 20rpx;
}

.store-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.store-title {
  display: flex;
  align-items: center;
}

.store-name {
  font-size: 40rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.store-type {
  margin-left: 16rpx;
  padding: 4rpx 12rpx;
  border-radius: 6rpx;
  background: #f2f2f2;
  font-size: 22rpx;
  color: #8a8a8a;
}

.switch {
  font-size: 26rpx;
  color: #8a8a8a;
  padding: 8rpx 0 8rpx 16rpx;
}

.store-desc {
  display: block;
  margin-top: 16rpx;
  font-size: 26rpx;
  color: #666;
  line-height: 1.7;
}

.store-address {
  display: block;
  margin-top: 12rpx;
  font-size: 26rpx;
  color: #a0a0a0;
  line-height: 1.7;
}

.store-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 20rpx;
  padding-top: 20rpx;
  border-top: 1px solid #f0f0f0;
  font-size: 26rpx;
  color: #666;
}

.phone {
  color: #1f1f1f;
}

.store-empty {
  display: block;
  margin-top: 16rpx;
  font-size: 26rpx;
  color: #a0a0a0;
}

/* ---------- 近期活动 ---------- */
.section {
  margin-top: 32rpx;
}

.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 20rpx;
  padding: 0 8rpx;
}

.section-title {
  font-size: 32rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.section-more {
  font-size: 26rpx;
  color: #8a8a8a;
}

.activity {
  display: flex;
  align-items: center;
  padding: 28rpx 32rpx;
  margin-bottom: 16rpx;
  background: #fff;
  border-radius: 20rpx;
}

.activity-left {
  width: 150rpx;
  flex-shrink: 0;
}

.activity-value {
  display: block;
  font-size: 36rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.activity-cond {
  display: block;
  margin-top: 4rpx;
  font-size: 22rpx;
  color: #a0a0a0;
}

.activity-right {
  flex: 1;
  min-width: 0;
}

.activity-name {
  display: block;
  font-size: 28rpx;
  color: #1f1f1f;
}

.activity-sub {
  display: block;
  margin-top: 8rpx;
  font-size: 22rpx;
  color: #a0a0a0;
}

.activity-btn {
  flex-shrink: 0;
  margin-left: 16rpx;
  padding: 10rpx 32rpx;
  background: #1f1f1f;
  color: #fff;
  font-size: 26rpx;
  border-radius: 32rpx;
}

.activity-btn.done {
  background: #f0f0f0;
  color: #b0b0b0;
}

.hint {
  padding: 60rpx 0;
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

/* ---------- 去点餐 ---------- */
.cta {
  margin-top: 40rpx;
  height: 92rpx;
  line-height: 92rpx;
  text-align: center;
  background: #1f1f1f;
  color: #fff;
  font-size: 32rpx;
  border-radius: 16rpx;
}

.cta.disabled {
  background: #c8c8c8;
}

.footnote {
  display: block;
  margin-top: 28rpx;
  padding: 0 8rpx 60rpx;
  font-size: 24rpx;
  color: #b0b0b0;
  line-height: 1.9;
}

/* ---------- 门店选择弹层 ---------- */
.mask {
  position: fixed;
  left: 0;
  right: 0;
  top: 0;
  /* 同 menu.vue 里那条：这一页也是 tab 页，弹层贴到屏幕最底下会被 H5 的
     tabBar 压住一截。`--window-bottom` 小程序里是 0、H5 里是 tabBar 的高度 */
  bottom: var(--window-bottom);
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: flex-end;
  z-index: 10;
}

.sheet {
  width: 100%;
  max-height: 75vh;
  background: #fff;
  border-radius: 24rpx 24rpx 0 0;
  display: flex;
  flex-direction: column;
}

.sheet-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 32rpx;
  border-bottom: 1px solid #f0f0f0;
}

.sheet-title {
  font-size: 32rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.sheet-close {
  padding: 0 12rpx;
  font-size: 40rpx;
  color: #a0a0a0;
}

.sheet-body {
  flex: 1;
  max-height: 60vh;
  padding: 16rpx 32rpx 32rpx;
  box-sizing: border-box;
}

.store-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 28rpx 0;
  border-bottom: 1px solid #f5f5f5;
}

.option-main {
  flex: 1;
  min-width: 0;
}

.option-name {
  display: block;
  font-size: 30rpx;
  color: #1f1f1f;
}

.store-option.active .option-name {
  font-weight: 600;
}

.option-address {
  display: block;
  margin-top: 8rpx;
  font-size: 24rpx;
  color: #a0a0a0;
}

.option-hours {
  display: block;
  margin-top: 6rpx;
  font-size: 22rpx;
  color: #b0b0b0;
}

.option-check {
  margin-left: 16rpx;
  font-size: 32rpx;
  color: #1f1f1f;
}
</style>