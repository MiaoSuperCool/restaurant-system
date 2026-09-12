<template>
  <view class="page">
    <view v-if="loading" class="hint">加载中…</view>

    <view v-else-if="list.length === 0" class="hint">
      <text>还没有下过单</text>
      <text class="hint-sub">去首页选个门店开始点单吧</text>
      <view class="go-btn" @tap="goHome">去点单</view>
    </view>

    <view v-else class="list">
      <view
        v-for="record in list"
        :key="record.order_no"
        class="card"
        @tap="openDetail(record)"
      >
        <view class="card-head">
          <text class="store">{{ record.store_name }}</text>
          <text class="status" :class="record.status">{{ record.statusLabel }}</text>
        </view>
        <text class="order-no">{{ record.order_no }}</text>
        <view class="card-foot">
          <text class="amount">{{ formatPrice(record.payable_amount) }}</text>
          <text class="time">{{ formatTime(record.created_at) }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { ref } from 'vue'
import { getOrder } from '@/api/public'
import { getMyOrders } from '@/stores/myOrders'
import type { MyOrderBrief } from '@/stores/myOrders'
import { formatPrice, formatTime } from '@/utils/format'

/** 本地记录 + 从后端查到的最新状态 */
interface OrderRecord extends MyOrderBrief {
  status: string
  statusLabel: string
}

const list = ref<OrderRecord[]>([])
const loading = ref(true)

/**
 * 拉取每条订单的最新状态
 *
 * 为什么是「本地记录 + 逐个查」而不是「一个列表接口」：
 * 一期顾客不登录，服务端不知道「我」是谁，没法给一个「我的订单」接口。
 * 二期做完会员登录之后，这里就该换成一次请求。
 */
async function loadOrders() {
  loading.value = true
  const briefs = getMyOrders()
  const records: OrderRecord[] = []

  for (const brief of briefs) {
    try {
      const order = await getOrder(brief.order_no, brief.query_token)
      records.push({
        ...brief,
        store_name: order.store_name || brief.store_name,
        payable_amount: order.payable_amount,
        status: order.status,
        statusLabel: order.status_label,
      })
    } catch {
      // 查不到就跳过——可能订单被清理了，或者凭据失效
    }
  }

  list.value = records
  loading.value = false
}

function openDetail(record: OrderRecord) {
  uni.navigateTo({
    url: `/pages/order/detail?orderNo=${record.order_no}&token=${record.query_token}`,
  })
}

function goHome() {
  uni.reLaunch({ url: '/pages/index/index' })
}

// onShow 而不是 onMounted：从详情页返回时状态可能已经变了，要重新拉
onShow(loadOrders)
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 24rpx;
}

.hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 160rpx 40rpx;
  font-size: 28rpx;
  color: #a0a0a0;
}

.hint-sub {
  font-size: 24rpx;
  margin-top: 12rpx;
}

.go-btn {
  margin-top: 40rpx;
  background: #1f1f1f;
  color: #fff;
  font-size: 28rpx;
  padding: 18rpx 56rpx;
  border-radius: 40rpx;
}

.card {
  background: #fff;
  border-radius: 16rpx;
  padding: 28rpx 32rpx;
  margin-bottom: 20rpx;
}

.card:active {
  background: #fafafa;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.store {
  font-size: 30rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.status {
  font-size: 24rpx;
  padding: 4rpx 16rpx;
  border-radius: 20rpx;
  background: #f2f2f2;
  color: #666;
}

.status.pending {
  background: #fdf0f0;
  color: #c45656;
}

.status.completed {
  background: #f0f7f0;
  color: #4a8a4a;
}

.order-no {
  display: block;
  font-size: 24rpx;
  color: #a0a0a0;
  margin-top: 12rpx;
}

.card-foot {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-top: 20rpx;
}

.amount {
  font-size: 32rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.time {
  font-size: 24rpx;
  color: #b0b0b0;
}
</style>
