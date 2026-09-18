<template>
  <view class="page">
    <view class="me">
      <view class="me-main">
        <text class="me-name">{{ staffName }}</text>
        <text class="me-meta">{{ roleText }}</text>
      </view>
      <text class="logout" @tap="handleLogout">退出</text>
    </view>

    <view class="today">
      <view class="stat">
        <text class="stat-value">{{ home?.today.order_count ?? '—' }}</text>
        <text class="stat-label">今日订单</text>
      </view>
      <view class="stat">
        <text class="stat-value warn">{{ home?.today.pending_count ?? '—' }}</text>
        <text class="stat-label">待接单</text>
      </view>
      <view class="stat">
        <text class="stat-value">{{ formatPrice(home?.today.revenue ?? 0) }}</text>
        <text class="stat-label">今日营业额</text>
      </view>
    </view>

    <view class="entries">
      <view v-if="canCreateOrder" class="entry" @tap="go('/pages/order/new')">
        <text class="entry-title">代客点单</text>
        <text class="entry-sub">顾客在桌边点单，代他下单</text>
      </view>

      <view v-if="canViewOrder" class="entry" @tap="go('/pages/order/list')">
        <text class="entry-title">{{ canReceive ? '接单 / 出单' : '看单' }}</text>
        <text class="entry-sub">
          <!-- 老板/运营是全部范围，看到的是**各店**的单；一线的人只看本店 -->
          {{ canReceive ? '接单、完成后到收款'
            : dataScope === 'all' ? '实时刷新，看各家店还有哪些单没做'
            : '实时刷新，看本店还有哪些单没做' }}
        </text>
      </view>

      <view v-if="canVerify" class="entry" @tap="go('/pages/groupon/verify')">
        <text class="entry-title">团购券核销</text>
        <text class="entry-sub">美团 / 抖音买的券，抵这一单的钱</text>
      </view>

      <!-- 第四个入口只给店长和老板看：一线的人不需要「今天做了多少生意」，
           而且这个数也不该给他们（后端要 report:store / report:all） -->
      <view v-if="canSeeReport" class="entry" @tap="go('/pages/report/report')">
        <text class="entry-title">经营</text>
        <text class="entry-sub">今天做了多少、哪家店做得好</text>
      </view>
    </view>

    <text class="footnote">
      菜单、员工、门店那些在电脑上做——手机屏幕塞不下，硬塞进去只会让每件事都变难用。
      这里放的是「站在店里能干的活」，外加店长和老板要看的那一眼数。
    </text>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getHome, logout } from '@/api/auth'
import type { HomeData } from '@/api/auth'
import { authState, clearSession, hasAnyPermission, hasPermission, setSession } from '@/stores/auth'
import { formatPrice } from '@/utils/format'

const home = ref<HomeData | null>(null)

const staffName = computed(() => authState.staff?.real_name || authState.staff?.username || '')
const roleText = computed(() => {
  const roles = authState.staff?.roles?.map((role) => role.name).join('、')
  const store = authState.staff?.store_name
  return [store || '总部', roles].filter(Boolean).join(' · ')
})

// 按权限渲染入口——**只是体验层**，后端每个接口都会重新判权
const canCreateOrder = computed(() => hasPermission('order:create'))
const canViewOrder = computed(() => hasPermission('order:view'))
const canReceive = computed(() => hasPermission('order:receive'))
const canVerify = computed(() => hasPermission('coupon:verify'))
// 看数的入口：店长（本店）和老板（全公司）有，收银员/服务员没有
const canSeeReport = computed(() => hasAnyPermission('report:store', 'report:all'))
// 老板是全部范围，界面上几处「本店」的说法对他不成立
const dataScope = computed(() => authState.data_scope)

async function loadHome() {
  try {
    const data = await getHome()
    home.value = data
    // **顺手用最新的权限覆盖本地缓存**：改了角色不用重新登录就生效，
    // 和后端 `/index` 那个接口的说明一致（网页端也是这么做的）
    setSession({ staff: data.staff, permissions: data.permissions, data_scope: data.data_scope })
  } catch {
    // 401 已经在 request.ts 里跳登录页了
  }
}

function go(url: string) {
  uni.navigateTo({ url })
}

async function handleLogout() {
  try {
    await logout()
  } catch {
    // 就算请求失败（断网、token 已经废了）也要把本地清掉——
    // 不然会卡在「点了没反应」的状态
  }
  clearSession()
  uni.reLaunch({ url: '/pages/login/login' })
}

// 用 onShow 不用 onMounted：从点单页/出单页返回时也要刷新，
// 「待接单」那个数刚做完一单就该变
onShow(loadHome)
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 32rpx;
  box-sizing: border-box;
}

.me {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 32rpx;
  background: #fff;
  border-radius: 20rpx;
}

.me-name {
  display: block;
  font-size: 36rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.me-meta {
  display: block;
  margin-top: 8rpx;
  font-size: 26rpx;
  color: #a0a0a0;
}

.logout {
  font-size: 28rpx;
  color: #8a8a8a;
  padding: 12rpx 8rpx;
}

.today {
  display: flex;
  margin-top: 24rpx;
  padding: 32rpx 0;
  background: #fff;
  border-radius: 20rpx;
}

.stat {
  flex: 1;
  text-align: center;
}

.stat-value {
  display: block;
  font-size: 40rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.stat-value.warn {
  color: #d48806;
}

.stat-label {
  display: block;
  margin-top: 8rpx;
  font-size: 24rpx;
  color: #a0a0a0;
}

.entries {
  margin-top: 24rpx;
}

.entry {
  padding: 36rpx 32rpx;
  margin-bottom: 20rpx;
  background: #fff;
  border-radius: 20rpx;
}

.entry:active {
  background: #f0f0f0;
}

.entry-title {
  display: block;
  font-size: 34rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.entry-sub {
  display: block;
  margin-top: 10rpx;
  font-size: 26rpx;
  color: #a0a0a0;
}

.footnote {
  display: block;
  margin-top: 40rpx;
  font-size: 24rpx;
  color: #b0b0b0;
  line-height: 1.8;
}
</style>