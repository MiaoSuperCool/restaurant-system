<template>
  <view class="page">
    <view class="hero">
      <text class="hero-label">接下来 {{ RANGE_DAYS }} 天</text>
      <text class="hero-value">{{ data?.total ?? 0 }}</text>
      <text class="hero-sub">个班 · {{ workdayCount }} 天要来店里</text>
    </view>

    <view v-if="!days.length" class="empty">
      <text class="empty-text">这段时间还没有给你排班</text>
      <text class="empty-sub">店长排好之后这里就有了</text>
    </view>

    <view v-for="day in days" :key="day.date" class="day">
      <view class="day-head">
        <text class="day-title">{{ day.relative || day.weekday }}</text>
        <text class="day-date">{{ day.date.slice(5) }} {{ day.weekday }}</text>
      </view>
      <view v-for="item in day.shifts" :key="item.id" class="shift">
        <text class="shift-name">{{ item.shift_name }}</text>
        <text class="shift-time">{{ item.shift_time_range }}</text>
      </view>
    </view>

    <text class="footnote">
      这是排班，不是考勤——它只管「你哪天来、几点到几点」。
      一天两个班是餐饮里的两头班（早上备菜、中午歇、晚上再来），不是排重了。
    </text>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getMySchedule } from '@/api/schedule'
import type { MySchedule } from '@/api/types'

const RANGE_DAYS = 14

const data = ref<MySchedule | null>(null)

const days = computed(() => data.value?.days ?? [])

/** 有几个「日子」要上班——两头班那天算一天，不是两天 */
const workdayCount = computed(() => days.value.length)

async function load() {
  try {
    data.value = await getMySchedule({ days: RANGE_DAYS })
  } catch {
    // request.ts 已经弹了提示（没权限码是 403，但入口本来就不会显示）
  }
}

// onShow：排班是店长那边随时会改的，从别处回来就重拉一次
onShow(load)
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 24rpx;
  box-sizing: border-box;
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

.empty {
  padding: 100rpx 40rpx;
  margin-top: 20rpx;
  background: #fff;
  border-radius: 20rpx;
  text-align: center;
}

.empty-text {
  display: block;
  font-size: 28rpx;
  color: #8a8a8a;
}

.empty-sub {
  display: block;
  margin-top: 12rpx;
  font-size: 24rpx;
  color: #b0b0b0;
}

.day {
  padding: 28rpx 32rpx;
  margin-top: 20rpx;
  background: #fff;
  border-radius: 20rpx;
}

.day-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 16rpx;
}

.day-title {
  font-size: 30rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.day-date {
  font-size: 24rpx;
  color: #a0a0a0;
}

.shift {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20rpx 24rpx;
  margin-top: 12rpx;
  background: #f5f6f8;
  border-radius: 12rpx;
}

.shift-name {
  font-size: 28rpx;
  color: #1f1f1f;
}

.shift-time {
  font-size: 26rpx;
  color: #5a5a5a;
}

.footnote {
  display: block;
  padding: 32rpx 8rpx 60rpx;
  font-size: 22rpx;
  color: #b0b0b0;
  line-height: 1.9;
}
</style>