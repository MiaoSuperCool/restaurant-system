<template>
  <view class="page">
    <view class="tabs">
      <text
        v-for="item in RANGES"
        :key="item.days"
        class="tab"
        :class="{ active: days === item.days }"
        @tap="switchRange(item.days)"
      >
        {{ item.label }}
      </text>
      <text class="range">{{ rangeText }}</text>
    </view>

    <view class="hero">
      <text class="hero-label">营业额</text>
      <text class="hero-value">{{ formatPrice(summary.revenue) }}</text>
      <text class="hero-sub">
        {{ summary.order_count }} 单 · 客单价 {{ formatPrice(summary.avg_order_amount) }}
      </text>
    </view>

    <view class="row">
      <view class="cell">
        <text class="cell-value">{{ formatPrice(summary.refund_amount) }}</text>
        <text class="cell-label">退款</text>
      </view>
      <view class="cell">
        <text class="cell-value">{{ summary.cancelled_count }}</text>
        <text class="cell-label">取消单</text>
      </view>
    </view>

    <!-- 「今天」只有一天，一根柱子画不出「趋势」——那一档就别放这张图了 -->
    <view v-if="days > 1" class="panel">
      <text class="panel-title">{{ rangeText }}营业额</text>
      <view class="bars">
        <view v-for="row in trend" :key="row.date" class="bar-col">
          <text class="bar-value">{{ row.revenue ? formatPrice(row.revenue) : '' }}</text>
          <view class="bar-track">
            <view class="bar" :style="{ height: barLength(row.revenue, trendMax) }" />
          </view>
          <text class="bar-label">{{ row.date.slice(5) }}</text>
        </view>
      </view>
    </view>

    <!-- 店长只会看到自己一家，那就没有「对比」可言 -->
    <view v-if="byStore.length > 1" class="panel">
      <text class="panel-title">门店对比</text>
      <view v-for="row in byStore" :key="row.store_id" class="hbar-row">
        <text class="hbar-label">{{ row.store_name }}</text>
        <view class="hbar-track">
          <view class="hbar-fill" :style="{ width: barLength(row.revenue, storeMax) }" />
        </view>
        <text class="hbar-value">{{ formatPrice(row.revenue) }}</text>
      </view>
    </view>

    <text class="footnote">
      口径：营业额 = 已收 − 已退，排除已取消的单；按下单时间算
      （和订单号里的日期、日结对账同一个口径），不是收款时间。
      支付构成、菜品排行、时段分布那些在电脑上看得更全。
    </text>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getReportOverview } from '@/api/reports'
import type { ReportOverview } from '@/api/types'
import { formatPrice } from '@/utils/format'

const RANGES = [
  { days: 1, label: '今天' },
  { days: 7, label: '近 7 天' },
  { days: 30, label: '近 1 月' },
]

const days = ref(1)
const data = ref<ReportOverview | null>(null)

/** 没数据时给一份「0 的样子」，模板里就不用到处写 `?.` */
const summary = computed(() => data.value?.summary ?? {
  revenue: 0, order_count: 0, avg_order_amount: 0, refund_amount: 0, cancelled_count: 0,
})
const trend = computed(() => data.value?.trend ?? [])
const byStore = computed(() => data.value?.by_store ?? [])

const rangeText = computed(() => {
  const range = data.value?.range
  if (!range) return ''
  return range.days === 1 ? '今天' : `${range.start.slice(5)} ~ ${range.end.slice(5)}`
})

const trendMax = computed(() => Math.max(...trend.value.map((row) => row.revenue), 0))
const storeMax = computed(() => Math.max(...byStore.value.map((row) => row.revenue), 0))

/**
 * 长度：`base` 撑满，其余按比例
 *
 * 和电脑上那个报表页同一套做法——有值但很小时给个 4% 的底
 * （「卖了 1 块钱」和「压根没卖」是两回事），真的为 0 就不画
 * （空着那一格才说明这天没生意）。
 */
function barLength(value: number, base: number): string {
  if (base <= 0) return '0%'
  return `${Math.max((value / base) * 100, value > 0 ? 4 : 0)}%`
}

async function load() {
  try {
    data.value = await getReportOverview({ days: days.value })
  } catch {
    // request.ts 已经弹了提示（没权限码是 403，但入口本来就不会显示）
  }
}

function switchRange(value: number) {
  if (days.value === value) return
  days.value = value
  load()
}

// onShow：从别处返回时也可能过了一段时间，重拉一次
onShow(load)
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 24rpx;
  box-sizing: border-box;
}

.tabs {
  display: flex;
  align-items: center;
  margin-bottom: 24rpx;
}

.tab {
  padding: 10rpx 28rpx;
  margin-right: 16rpx;
  border-radius: 32rpx;
  font-size: 26rpx;
  color: #1f1f1f;
  background: #fff;
}

.tab.active {
  background: #1f1f1f;
  color: #fff;
}

.range {
  margin-left: auto;
  font-size: 22rpx;
  color: #a0a0a0;
}

.hero {
  padding: 40rpx 32rpx;
  background: #1f1f1f;
  border-radius: 20rpx;
}

.hero-label {
  display: block;
  font-size: 24rpx;
  color: #b0b0b0;
}

.hero-value {
  display: block;
  margin-top: 12rpx;
  font-size: 72rpx;
  font-weight: 600;
  color: #fff;
  line-height: 1.1;
}

.hero-sub {
  display: block;
  margin-top: 12rpx;
  font-size: 26rpx;
  color: #b0b0b0;
}

.row {
  display: flex;
  margin-top: 20rpx;
}

.cell {
  flex: 1;
  padding: 28rpx 32rpx;
  margin-right: 20rpx;
  background: #fff;
  border-radius: 20rpx;
}

.cell:last-child {
  margin-right: 0;
}

.cell-value {
  display: block;
  font-size: 36rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.cell-label {
  display: block;
  margin-top: 8rpx;
  font-size: 22rpx;
  color: #a0a0a0;
}

.panel {
  padding: 28rpx 32rpx;
  margin-top: 20rpx;
  background: #fff;
  border-radius: 20rpx;
}

.panel-title {
  display: block;
  font-size: 28rpx;
  font-weight: 600;
  color: #1f1f1f;
  margin-bottom: 24rpx;
}

/* ---------- 柱状图（纯 CSS，和电脑上那个报表页一个做法） ---------- */

.bars {
  display: flex;
  align-items: flex-end;
  height: 220rpx;
}

.bar-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
}

.bar-value {
  font-size: 18rpx;
  color: #8a8a8a;
  margin-bottom: 6rpx;
  white-space: nowrap;
}

.bar-track {
  flex: 1;
  width: 70%;
  display: flex;
  align-items: flex-end;
}

.bar {
  width: 100%;
  background: #1f1f1f;
  border-radius: 4rpx 4rpx 0 0;
}

.bar-label {
  margin-top: 10rpx;
  font-size: 18rpx;
  color: #a0a0a0;
  white-space: nowrap;
}

/* ---------- 横条 ---------- */

.hbar-row {
  display: flex;
  align-items: center;
  margin-bottom: 20rpx;
}

.hbar-label {
  width: 150rpx;
  flex-shrink: 0;
  font-size: 24rpx;
  color: #1f1f1f;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hbar-track {
  flex: 1;
  height: 20rpx;
  background: #f0f0f0;
  border-radius: 10rpx;
  overflow: hidden;
}

.hbar-fill {
  height: 100%;
  background: #1f1f1f;
  border-radius: 10rpx;
}

.hbar-value {
  width: 140rpx;
  flex-shrink: 0;
  text-align: right;
  font-size: 24rpx;
  color: #1f1f1f;
}

.footnote {
  display: block;
  padding: 32rpx 8rpx 60rpx;
  font-size: 22rpx;
  color: #b0b0b0;
  line-height: 1.9;
}
</style>