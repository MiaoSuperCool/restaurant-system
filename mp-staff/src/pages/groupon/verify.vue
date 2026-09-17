<template>
  <view class="page">
    <view class="step">
      <text class="step-title">① 找到这单</text>
      <view class="search">
        <input
          v-model="keyword"
          class="input"
          placeholder="输单号后几位，或顾客报的单号"
          :disabled="loading"
          @confirm="handleSearch"
        />
        <button class="btn-dark" :disabled="loading" @tap="handleSearch">查</button>
      </view>

      <view v-if="order" class="order">
        <view class="order-line">
          <text class="order-no">{{ order.order_no }}</text>
          <text class="order-status">{{ order.status_label }}</text>
        </view>
        <view class="order-line">
          <text class="order-money">应付 {{ formatPrice(order.payable_amount) }}</text>
          <text class="order-money">
            已收 {{ formatPrice(order.paid_amount) }} · 还差
            {{ formatPrice(order.payable_amount - order.paid_amount) }}
          </text>
        </view>
        <text class="order-hint">{{ order.source_label }} · {{ formatTime(order.created_at) }}</text>
      </view>

      <text v-else-if="searched && !loading" class="empty">没找到这单，单号对不对？</text>
    </view>

    <view class="step">
      <text class="step-title">② 输券码</text>

      <view class="field">
        <text class="label">券码</text>
        <input
          v-model="code"
          class="input"
          placeholder="美团券码一般以 MT 开头"
          :disabled="submitting"
          @confirm="handleVerify"
        />
      </view>

      <view class="field">
        <text class="label">平台</text>
        <view class="platforms">
          <text
            v-for="item in PLATFORMS"
            :key="item.value"
            class="platform"
            :class="{ on: platform === item.value }"
            @tap="platform = item.value"
          >
            {{ item.label }}
          </text>
        </view>
      </view>

      <view class="field">
        <text class="label">券面额</text>
        <input v-model="amount" class="input" type="digit" placeholder="券上印的金额" />
      </view>

      <view class="note">
        <text class="note-line">券只能抵扣，不找零：面额超过还差的钱会被拒。</text>
        <text class="note-line">同一张券核销第二次也会被拒——券码在数据库里是唯一的。</text>
      </view>

      <button
        class="btn-dark wide"
        :disabled="!order || submitting"
        @tap="handleVerify"
      >
        {{ submitting ? '核销中…' : '核销' }}
      </button>
    </view>

    <view class="footnote">
      <text class="note-line">
        这个页面是手工输入券码的，没有真的调美团/抖音的核销接口——
      </text>
      <text class="note-line">真对接时这里会变成扫一扫，面额也不用人工填。</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { getOrders, verifyGroupon } from '@/api/orders'
import type { Order } from '@/api/types'
import { formatPrice, formatTime } from '@/utils/format'

const PLATFORMS = [
  { value: 'meituan', label: '美团' },
  { value: 'douyin', label: '抖音' },
]

const keyword = ref('')
const order = ref<Order | null>(null)
const searched = ref(false)
const loading = ref(false)

const code = ref('')
const platform = ref('meituan')
const amount = ref('')
const submitting = ref(false)

/** 还差多少钱没付——券最多抵这么多，多了后端会拒 */
const unpaid = computed(() => {
  if (!order.value) return 0
  return Math.max(order.value.payable_amount - order.value.paid_amount, 0)
})

async function handleSearch() {
  const word = keyword.value.trim()
  if (!word) {
    uni.showToast({ title: '先输个单号', icon: 'none' })
    return
  }

  loading.value = true
  searched.value = false
  try {
    // 用 order:view 那个列表接口按单号搜，不另开后门——
    // 核销的人本来就要能看到订单（收银员/店长都有 order:view），
    // 单开一个「只要有 coupon:verify 就能查任意订单」的口子反而更松
    const data = await getOrders({ search: word, per_page: 1 })
    order.value = data.orders[0] ?? null
    if (order.value) {
      amount.value = unpaid.value.toFixed(2)
    }
  } catch {
    // request.ts 已经弹了提示
  } finally {
    loading.value = false
    searched.value = true
  }
}

async function handleVerify() {
  if (!order.value || submitting.value) return
  if (!code.value.trim()) {
    uni.showToast({ title: '券码不能为空', icon: 'none' })
    return
  }
  const value = Number(amount.value)
  if (!value || value <= 0) {
    uni.showToast({ title: '券面额要大于 0', icon: 'none' })
    return
  }

  submitting.value = true
  try {
    const data = await verifyGroupon(order.value.id, {
      code: code.value.trim(),
      platform: platform.value,
      amount: value,
    })

    uni.showModal({
      title: '核销成功',
      content: `券 ¥${value.toFixed(2)} 已抵扣\n还差 ${formatPrice(
        data.order.payable_amount - data.order.paid_amount
      )}`,
      showCancel: false,
      success: () => {
        // 回到这一页的开头：换下一单
        order.value = null
        code.value = ''
        amount.value = ''
        keyword.value = ''
        searched.value = false
      },
    })
  } catch {
    // request.ts 弹的是后端那句（券码已核销 / 面额超过未付部分 / 不在数据范围）
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  padding: 24rpx;
  background: #f5f5f5;
  box-sizing: border-box;
}

.step {
  padding: 32rpx;
  margin-bottom: 20rpx;
  background: #fff;
  border-radius: 20rpx;
}

.step-title {
  display: block;
  margin-bottom: 24rpx;
  font-size: 30rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.search {
  display: flex;
  align-items: center;
}

.input {
  flex: 1;
  height: 84rpx;
  padding: 0 24rpx;
  background: #f7f7f7;
  border-radius: 12rpx;
  font-size: 28rpx;
}

.btn-dark {
  margin-left: 16rpx;
  padding: 0 36rpx;
  height: 84rpx;
  line-height: 84rpx;
  background: #1f1f1f;
  color: #fff;
  font-size: 28rpx;
  border-radius: 12rpx;
}

.btn-dark[disabled] {
  background: #c0c0c0;
}

.wide {
  width: 100%;
  margin: 32rpx 0 0;
}

.order {
  margin-top: 24rpx;
  padding: 24rpx;
  background: #f7f7f7;
  border-radius: 12rpx;
}

.order-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12rpx;
}

.order-no {
  font-size: 28rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.order-status {
  font-size: 24rpx;
  color: #8a8a8a;
}

.order-money {
  font-size: 26rpx;
  color: #1f1f1f;
}

.order-hint {
  display: block;
  margin-top: 8rpx;
  font-size: 24rpx;
  color: #a0a0a0;
}

.empty {
  display: block;
  padding: 32rpx 0 0;
  font-size: 26rpx;
  color: #a0a0a0;
}

.field {
  margin-bottom: 28rpx;
}

.label {
  display: block;
  margin-bottom: 12rpx;
  font-size: 26rpx;
  color: #8a8a8a;
}

.platforms {
  display: flex;
}

.platform {
  padding: 14rpx 36rpx;
  margin-right: 16rpx;
  border: 1px solid #e0e0e0;
  border-radius: 32rpx;
  font-size: 26rpx;
  color: #1f1f1f;
}

.platform.on {
  border-color: #1f1f1f;
  background: #1f1f1f;
  color: #fff;
}

.note {
  margin-bottom: 8rpx;
}

.note-line {
  display: block;
  font-size: 24rpx;
  color: #a0a0a0;
  line-height: 1.8;
}

.footnote {
  padding: 24rpx 12rpx 48rpx;
}

.footnote .note-line {
  color: #b0b0b0;
}
</style>