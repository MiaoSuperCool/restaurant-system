<template>
  <view class="page">
    <view v-if="loading" class="hint">加载中…</view>

    <view v-else-if="!order" class="hint">
      <text>订单查不到</text>
      <text class="hint-sub">可能是链接过期，或者查询凭据不对</text>
    </view>

    <template v-else>
      <!-- 状态卡 -->
      <view class="status-card">
        <text class="status">{{ order.status_label }}</text>
        <text class="status-sub">{{ statusHint }}</text>
        <text class="order-no">{{ order.order_no }}</text>
      </view>

      <!-- 明细 -->
      <view class="card">
        <view class="card-title">菜品</view>
        <view v-for="item in order.items" :key="item.id" class="item">
          <view class="item-main">
            <text class="item-name">{{ item.dish_name }}</text>
            <text v-if="item.options_text" class="item-options">{{ item.options_text }}</text>
          </view>
          <text class="item-qty">× {{ item.quantity }}</text>
          <text class="item-subtotal">{{ formatPrice(item.subtotal) }}</text>
        </view>

        <view class="amount-row">
          <text>应付</text>
          <text class="amount-strong">{{ formatPrice(order.payable_amount) }}</text>
        </view>
        <view v-if="order.paid_amount > 0" class="amount-row">
          <text>已付</text>
          <text>{{ formatPrice(order.paid_amount) }}</text>
        </view>
        <view v-if="order.refunded_amount > 0" class="amount-row refunded">
          <text>已退</text>
          <text>-{{ formatPrice(order.refunded_amount) }}</text>
        </view>
      </view>

      <!-- 门店与说明 -->
      <view class="card">
        <view class="info-row">
          <text class="info-label">门店</text>
          <text>{{ order.store_name }}</text>
        </view>
        <view class="info-row">
          <text class="info-label">取餐方式</text>
          <text>{{ order.source_label }}</text>
        </view>
        <view class="info-row">
          <text class="info-label">下单时间</text>
          <text>{{ formatTime(order.created_at) }}</text>
        </view>
        <view v-if="order.remark" class="info-row">
          <text class="info-label">备注</text>
          <text>{{ order.remark }}</text>
        </view>
      </view>

      <!-- 支付记录 -->
      <view v-if="order.payments && order.payments.length" class="card">
        <view class="card-title">支付记录</view>
        <view v-for="payment in order.payments" :key="payment.id" class="info-row">
          <text class="info-label">{{ payment.method_label }}</text>
          <text>{{ formatPrice(payment.amount) }}</text>
        </view>
      </view>

      <view class="actions">
        <view v-if="canPay" class="primary-btn" @tap="handlePay">立即支付</view>
        <view v-if="canCancel" class="ghost-btn" @tap="handleCancel">取消订单</view>
        <view class="ghost-btn" @tap="goMyOrders">我的订单</view>
      </view>

      <view class="foot-note">
        一期演示：支付是【模拟】的，没有真的对接微信支付。
        真实的支付要调 wx.requestPayment 并处理异步回调（见后端 wechat_pay.py）。
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { cancelOrder, getOrder, payOrder } from '@/api/public'
import type { Order } from '@/api/types'
import { formatPrice, formatTime } from '@/utils/format'

const orderNo = ref('')
const token = ref('')
const order = ref<Order | null>(null)
const loading = ref(true)
const busy = ref(false)

const statusHint = computed(() => {
  const current = order.value
  if (!current) return ''
  const hints: Record<string, string> = {
    pending: '已下单，等待门店接单',
    accepted: '门店已接单，正在准备',
    completed: '已完成，欢迎再次光临',
    cancelled: '订单已取消',
  }
  return hints[current.status] || ''
})

const canPay = computed(() => {
  const current = order.value
  return current !== null && current.status !== 'cancelled' && current.paid_amount < current.payable_amount
})

const canCancel = computed(() => {
  const current = order.value
  return current !== null && current.status === 'pending' && current.refundable_amount === 0
})

async function loadOrder() {
  loading.value = true
  try {
    order.value = await getOrder(orderNo.value, token.value)
  } catch {
    order.value = null
  } finally {
    loading.value = false
  }
}

async function handlePay() {
  if (busy.value) return
  busy.value = true
  try {
    await payOrder(orderNo.value, token.value)
    uni.showToast({ title: '支付成功', icon: 'success' })
    await loadOrder()
  } catch {
    // request.ts 已经弹了提示
  } finally {
    busy.value = false
  }
}

function handleCancel() {
  uni.showModal({
    title: '取消订单',
    content: '确定取消这一单吗？',
    success: async (res) => {
      if (!res.confirm) return
      try {
        await cancelOrder(orderNo.value, token.value)
        uni.showToast({ title: '已取消', icon: 'none' })
        await loadOrder()
      } catch {
        // request.ts 已经弹了提示
      }
    },
  })
}

function goMyOrders() {
  uni.navigateTo({ url: '/pages/orders/orders' })
}

onLoad((query) => {
  orderNo.value = query?.orderNo || ''
  token.value = query?.token || ''
  loadOrder()
})
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 24rpx 24rpx 60rpx;
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

.status-card {
  background: #1f1f1f;
  border-radius: 16rpx;
  padding: 40rpx 32rpx;
  display: flex;
  flex-direction: column;
  margin-bottom: 20rpx;
}

.status {
  font-size: 40rpx;
  font-weight: 600;
  color: #fff;
}

.status-sub {
  font-size: 26rpx;
  color: #b0b0b0;
  margin-top: 12rpx;
}

.order-no {
  font-size: 24rpx;
  color: #8a8a8a;
  margin-top: 20rpx;
}

.card {
  background: #fff;
  border-radius: 16rpx;
  padding: 28rpx 32rpx;
  margin-bottom: 20rpx;
}

.card-title {
  font-size: 26rpx;
  color: #8a8a8a;
  margin-bottom: 20rpx;
}

.item {
  display: flex;
  align-items: center;
  padding: 16rpx 0;
  border-bottom: 1rpx solid #f5f5f5;
}

.item-main {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.item-name {
  font-size: 28rpx;
  color: #1f1f1f;
}

.item-options {
  font-size: 22rpx;
  color: #a0a0a0;
  margin-top: 6rpx;
}

.item-qty {
  font-size: 26rpx;
  color: #8a8a8a;
  margin-right: 24rpx;
}

.item-subtotal {
  font-size: 28rpx;
  color: #1f1f1f;
}

.amount-row {
  display: flex;
  justify-content: space-between;
  padding: 14rpx 0;
  font-size: 28rpx;
  color: #666;
}

.amount-strong {
  font-size: 34rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.amount-row.refunded {
  color: #c45656;
}

.info-row {
  display: flex;
  padding: 12rpx 0;
  font-size: 28rpx;
  color: #1f1f1f;
}

.info-label {
  width: 160rpx;
  color: #8a8a8a;
}

.actions {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
  margin-top: 12rpx;
}

.primary-btn {
  background: #1f1f1f;
  color: #fff;
  font-size: 32rpx;
  text-align: center;
  padding: 28rpx;
  border-radius: 44rpx;
}

.ghost-btn {
  background: #fff;
  color: #1f1f1f;
  font-size: 30rpx;
  text-align: center;
  padding: 26rpx;
  border-radius: 44rpx;
  border: 1rpx solid #e5e5e5;
}

.foot-note {
  font-size: 22rpx;
  color: #b0b0b0;
  line-height: 1.7;
  margin-top: 40rpx;
  padding: 0 12rpx;
}
</style>
