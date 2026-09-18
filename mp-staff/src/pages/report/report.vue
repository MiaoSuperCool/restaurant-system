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
      <view class="panel-head">
        <text class="panel-title">{{ rangeText }}营业额</text>
        <!-- 手机上**没有鼠标悬停**，所以「看某一根具体是多少」改成点一下。
            （电脑端那边是 hover 出 tooltip，同一份数据两种交互） -->
        <text class="panel-pick">
          {{ picked
            ? `${picked.date.slice(5)} · ${formatPrice(picked.revenue)}`
            : `合计 ${formatPrice(summary.revenue)}` }}
        </text>
      </view>
      <view class="bars">
        <view
          v-for="(row, index) in trend"
          :key="row.date"
          class="bar-col"
          @tap="pickBar(index)"
        >
          <view class="bar-track">
            <view
              class="bar"
              :class="{ on: index === pickedIndex }"
              :style="{ height: barLength(row.revenue, trendMax) }"
            />
          </view>
          <!-- 刻度写**序号**（第几天），不写日期：30 天摊到每根才 11px，
               「09-12」要 35px，写日期就会挤出卡片。具体日期在顶上那行 -->
          <text class="bar-label">{{ compactTicks ? index + 1 : row.date.slice(5) }}</text>
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

    <view class="panel">
      <text class="panel-title">支付方式</text>
      <view v-if="!byMethod.length" class="empty">这段时间没有收款</view>
      <view v-for="row in byMethod" :key="row.method" class="hbar-row">
        <text class="hbar-label">{{ row.method_label }}</text>
        <view class="hbar-track">
          <view class="hbar-fill" :style="{ width: barLength(row.amount, methodTotal) }" />
        </view>
        <text class="hbar-value">
          {{ formatPrice(row.amount) }}
          <text class="hbar-sub">{{ methodPercent(row.amount) }}%</text>
        </text>
      </view>
    </view>

    <view class="panel">
      <text class="panel-title">热销菜品（按份数）</text>
      <view v-if="!topDishes.length" class="empty">这段时间没有卖出东西</view>
      <view v-for="row in topDishes" :key="row.dish_id" class="hbar-row">
        <text class="hbar-label">{{ row.dish_name }}</text>
        <view class="hbar-track">
          <view class="hbar-fill" :style="{ width: barLength(row.quantity, dishMax) }" />
        </view>
        <text class="hbar-value">
          {{ row.quantity }} 份
          <text class="hbar-sub">{{ formatPrice(row.amount) }}</text>
        </text>
      </view>
    </view>

    <view class="panel">
      <text class="panel-title">时段分布</text>
      <text class="panel-hint">这一块是给排班用的：哪个小时单最多，一眼看得出来</text>
      <view v-if="!byHour.length" class="empty">这段时间没有订单</view>
      <view v-else class="bars">
        <view v-for="row in byHour" :key="row.hour" class="bar-col">
          <view class="bar-track">
            <view class="bar" :style="{ height: barLength(row.order_count, hourMax) }" />
          </view>
          <text class="bar-label">{{ row.hour }}</text>
        </view>
      </view>
    </view>

    <text class="footnote">
      口径：营业额 = 已收 − 已退，排除已取消的单；按下单时间算
      （和订单号里的日期、日结对账同一个口径），不是收款时间。
      时段按本地时间分——「几点最忙」问的是店里墙上那个钟。
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
const byMethod = computed(() => data.value?.by_method ?? [])
const topDishes = computed(() => data.value?.top_dishes ?? [])
const byHour = computed(() => data.value?.by_hour ?? [])

/**
 * 趋势图上点中的那一根；`-1` = 没选，顶上显示**合计**
 *
 * 默认不选是因为「合计」比「今天」有用：选「近 1 月」的时候，
 * 默认显示最后一根（今天）会得到一个「¥0.00」——看着像数据没加载出来。
 * 再点同一根取消，回到合计。
 */
const pickedIndex = ref(-1)
const picked = computed(() => trend.value[pickedIndex.value] ?? null)

function pickBar(index: number) {
  pickedIndex.value = pickedIndex.value === index ? -1 : index
}

const rangeText = computed(() => {
  const range = data.value?.range
  if (!range) return ''
  return range.days === 1 ? '今天' : `${range.start.slice(5)} ~ ${range.end.slice(5)}`
})

/**
 * 刻度写序号还是写日期
 *
 * 两周以内写日期（「09-12」比「1」直观）；再长就写**序号**——
 * 30 天摊到每根才 11px，而「09-12」要 35px，写日期会被挤到溢出
 * （`nowrap` + flex 默认的 `min-width: auto`），只能抽稀，
 * 抽稀又会出现「有的有标签、有的没有」，看着乱。
 * 序号只要 11px 上下，30 个排得下，还整齐。
 */
const compactTicks = computed(() => trend.value.length > 14)

const trendMax = computed(() => Math.max(...trend.value.map((row) => row.revenue), 0))
const storeMax = computed(() => Math.max(...byStore.value.map((row) => row.revenue), 0))
const dishMax = computed(() => Math.max(...topDishes.value.map((row) => row.quantity), 0))
const hourMax = computed(() => Math.max(...byHour.value.map((row) => row.order_count), 0))
const methodTotal = computed(() =>
  byMethod.value.reduce((sum, row) => sum + row.amount, 0)
)

/** 某一笔支付占总额的百分比——这一组是「构成」，不是「排行」 */
function methodPercent(amount: number): string {
  if (methodTotal.value <= 0) return '0'
  return ((amount / methodTotal.value) * 100).toFixed(0)
}

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
    pickedIndex.value = -1          // 换了区间，之前点的那根不作数了
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

.panel-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 24rpx;
}

.panel-title {
  display: block;
  font-size: 28rpx;
  font-weight: 600;
  color: #1f1f1f;
  margin-bottom: 24rpx;
}

/* 标题行里的（趋势图那个）不要下间距——它的右边紧跟着选中的日期，
   下面紧跟着图，间距由 .panel-head 给 */
.panel-head .panel-title {
  margin-bottom: 0;
}

/* 点中的那一根的信息——手机上没得 hover，只能点 */
.panel-pick {
  font-size: 24rpx;
  color: #8a8a8a;
}

.panel-hint {
  display: block;
  /* 负边距只抵消标题 `margin-bottom` 的一部分——抵消过头的话
     副标题会贴到标题上（试过 -16rpx，两行字挤在一起了） */
  margin-top: -8rpx;
  margin-bottom: 24rpx;
  font-size: 22rpx;
  color: #a0a0a0;
}

.empty {
  padding: 40rpx 0;
  text-align: center;
  font-size: 24rpx;
  color: #a0a0a0;
}

/* ---------- 柱状图（纯 CSS，和电脑上那个报表页一个做法） ---------- */

.bars {
  display: flex;
  align-items: flex-end;
  height: 220rpx;
}

.bar-col {
  flex: 1;
  /* **不写这条的话 flex 默认 min-width: auto**，列会被里面的文字撑开
     （标签是 nowrap），一列撑宽、整排跟着溢出容器 */
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
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

/* 点中的那一根加深不了多少（本来就是黑的），改成两边留白把它凸显出来 */
.bar.on {
  background: #1f1f1f;
  box-shadow: 0 0 0 4rpx #d0d0d0;
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

.hbar-sub {
  display: block;
  font-size: 20rpx;
  color: #a0a0a0;
}

.footnote {
  display: block;
  padding: 32rpx 8rpx 60rpx;
  font-size: 22rpx;
  color: #b0b0b0;
  line-height: 1.9;
}
</style>