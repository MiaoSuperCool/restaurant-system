<template>
  <view class="page">
    <view class="tabs">
      <text
        v-for="item in TABS"
        :key="item.value"
        class="tab"
        :class="{ active: status === item.value }"
        @tap="switchTab(item.value)"
      >
        {{ item.label }}
      </text>
      <text class="refresh" @tap="load">刷新</text>
    </view>

    <view v-if="loading && orders.length === 0" class="hint">加载中…</view>

    <view v-else-if="orders.length === 0" class="hint">
      <text>这个状态下没有单子</text>
      <text class="hint-sub">
        {{ status === 'pending' ? '顾客下单后会出现在这里' : '换个状态看看' }}
      </text>
    </view>

    <scroll-view v-else class="list" scroll-y>
      <view v-for="order in orders" :key="order.id" class="card">
        <view class="card-head">
          <text class="order-no">{{ order.order_no }}</text>
          <text class="wait">{{ timeAgo(order.created_at) }}</text>
        </view>

        <view class="card-meta">
          <text class="tag">{{ order.source_label }}</text>
          <text v-if="order.remark" class="remark">{{ order.remark }}</text>
        </view>

        <view class="items">
          <view v-for="item in order.items || []" :key="item.id" class="item">
            <text class="item-name">
              {{ item.dish_name }}
              <text v-if="item.options && item.options.length" class="item-options">
                {{ item.options.map((o) => o.name).join(' / ') }}
              </text>
            </text>
            <text class="item-qty">×{{ item.quantity }}</text>
          </view>
        </view>

        <view class="card-foot">
          <view class="money">
            <text class="payable">{{ formatPrice(order.payable_amount) }}</text>
            <text class="paid">
              {{ order.is_paid ? '已收款' : `未收款（已收 ${formatPrice(order.paid_amount)}）` }}
            </text>
          </view>

          <view class="actions">
            <button
              v-if="canReceive && order.status === 'pending'"
              class="act primary"
              @tap="handleAccept(order)"
            >
              接单
            </button>
            <button
              v-if="canReceive && order.status === 'accepted'"
              class="act"
              @tap="handleComplete(order)"
            >
              完成
            </button>
            <text v-if="!canReceive" class="readonly">只读</text>
          </view>
        </view>
      </view>
    </scroll-view>

    <text class="footnote">
      {{ canReceive ? '「完成」之后到电脑上收款——手机上不收钱。' : '这个账号只能看单。' }}
    </text>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onPullDownRefresh, onShow } from '@dcloudio/uni-app'
import { acceptOrder, completeOrder, getOrders } from '@/api/orders'
import type { Order } from '@/api/types'
import { hasPermission } from '@/stores/auth'
import { formatPrice, timeAgo } from '@/utils/format'

const TABS = [
  { value: 'pending', label: '待接单' },
  { value: 'accepted', label: '已接单' },
  { value: 'completed', label: '已完成' },
]

const status = ref('pending')
const orders = ref<Order[]>([])
const loading = ref(false)

/** 能不能接单/完成。
 *
 * **后厨没有 `order:receive`**，所以这一页对他们来说是只读的——
 * 这和后端 RBAC 是一致的：后厨的职责是「看单做菜」，
 * 接单和完成是前厅（收银/值班/店长）的动作。界面上如实显示「只读」。
 */
const canReceive = computed(() => hasPermission('order:receive'))

async function load() {
  loading.value = true
  try {
    // 一次多拉几条：出单页是站着看的，翻页很烦
    const data = await getOrders({ status: status.value, per_page: 50 })
    orders.value = data.orders
  } catch {
    // request.ts 已经弹了提示
  } finally {
    loading.value = false
    uni.stopPullDownRefresh()
  }
}

function switchTab(value: string) {
  status.value = value
  orders.value = []
  load()
}

async function handleAccept(order: Order) {
  try {
    await acceptOrder(order.id)
    uni.showToast({ title: '已接单', icon: 'success' })
    load()
  } catch {
    // 别人抢先接了、或者状态已经变了，后端会拒
  }
}

async function handleComplete(order: Order) {
  try {
    await completeOrder(order.id)
    uni.showToast({ title: '已完成', icon: 'success' })
    load()
  } catch {
    // 已经完成过、或者状态不对
  }
}

// onShow 而不是 onMounted：从别处返回时要看到最新的单子
// （出单页开着一整天，靠手动刷新不现实）
onShow(load)
onPullDownRefresh(load)
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f5f5f5;
  box-sizing: border-box;
}

.tabs {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  padding: 16rpx 24rpx;
  background: #fff;
}

.tab {
  padding: 12rpx 24rpx;
  margin-right: 12rpx;
  border-radius: 32rpx;
  font-size: 26rpx;
  color: #1f1f1f;
  background: #f2f2f2;
}

.tab.active {
  background: #1f1f1f;
  color: #fff;
}

.refresh {
  margin-left: auto;
  padding: 12rpx 8rpx;
  font-size: 26rpx;
  color: #8a8a8a;
}

.list {
  flex: 1;
  padding: 20rpx 24rpx;
  box-sizing: border-box;
}

.card {
  padding: 28rpx;
  margin-bottom: 20rpx;
  background: #fff;
  border-radius: 16rpx;
}

.card-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.order-no {
  font-size: 28rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.wait {
  font-size: 24rpx;
  color: #d48806;
}

.card-meta {
  display: flex;
  align-items: center;
  margin-top: 12rpx;
}

.tag {
  padding: 4rpx 12rpx;
  margin-right: 12rpx;
  border-radius: 6rpx;
  background: #f2f2f2;
  font-size: 22rpx;
  color: #8a8a8a;
}

.remark {
  flex: 1;
  font-size: 24rpx;
  color: #d48806;
}

.items {
  margin-top: 20rpx;
  padding-top: 20rpx;
  border-top: 1px dashed #eee;
}

.item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12rpx;
}

.item-name {
  flex: 1;
  font-size: 28rpx;
  color: #1f1f1f;
}

.item-options {
  margin-left: 8rpx;
  font-size: 24rpx;
  color: #8a8a8a;
}

.item-qty {
  font-size: 28rpx;
  color: #1f1f1f;
}

.card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 20rpx;
  padding-top: 20rpx;
  border-top: 1px solid #f0f0f0;
}

.payable {
  display: block;
  font-size: 34rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.paid {
  display: block;
  margin-top: 4rpx;
  font-size: 22rpx;
  color: #a0a0a0;
}

.actions {
  display: flex;
  align-items: center;
}

.act {
  margin-left: 16rpx;
  padding: 0 32rpx;
  height: 68rpx;
  line-height: 68rpx;
  font-size: 26rpx;
  border-radius: 10rpx;
  background: #f2f2f2;
  color: #1f1f1f;
}

.act.primary {
  background: #1f1f1f;
  color: #fff;
}

.readonly {
  font-size: 24rpx;
  color: #b0b0b0;
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
  flex-shrink: 0;
  padding: 20rpx 32rpx 32rpx;
  font-size: 24rpx;
  color: #b0b0b0;
  text-align: center;
}
</style>