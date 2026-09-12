<template>
  <view class="page">
    <view class="hero">
      <text class="hero-title">欢迎光临</text>
      <text class="hero-sub">选一家门店开始点单</text>
    </view>

    <view v-if="loading" class="hint">加载中…</view>

    <view v-else-if="stores.length === 0" class="hint">
      <text>暂时没有营业中的门店</text>
      <text class="hint-sub">门店休息中或已停业时不会出现在这里</text>
    </view>

    <view v-else class="store-list">
      <view
        v-for="store in stores"
        :key="store.id"
        class="store-card"
        @tap="chooseStore(store)"
      >
        <view class="store-head">
          <text class="store-name">{{ store.name }}</text>
          <text class="store-code">{{ store.code }}</text>
        </view>
        <text class="store-address">{{ store.address || '（未填地址）' }}</text>
        <text v-if="store.phone" class="store-phone">{{ store.phone }}</text>
      </view>
    </view>

    <view class="footer">
      <text class="link" @tap="goMyOrders">我的订单 ›</text>
      <text class="version">一期演示 · 支付为模拟</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getStores } from '@/api/public'
import type { StoreBrief } from '@/api/types'

const stores = ref<StoreBrief[]>([])
const loading = ref(true)

async function loadStores() {
  loading.value = true
  try {
    const data = await getStores()
    stores.value = data.stores
  } catch {
    // request.ts 已经弹了提示
  } finally {
    loading.value = false
  }
}

function chooseStore(store: StoreBrief) {
  // 门店信息带过去，菜单页不用再查一次
  uni.navigateTo({
    url: `/pages/menu/menu?storeId=${store.id}&storeName=${encodeURIComponent(store.name)}`,
  })
}

function goMyOrders() {
  uni.navigateTo({ url: '/pages/orders/orders' })
}

onMounted(loadStores)
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 40rpx;
}

.hero {
  padding: 60rpx 40rpx 40rpx;
  display: flex;
  flex-direction: column;
}

.hero-title {
  font-size: 52rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.hero-sub {
  font-size: 26rpx;
  color: #8a8a8a;
  margin-top: 12rpx;
}

.hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 120rpx 40rpx;
  font-size: 28rpx;
  color: #a0a0a0;
}

.hint-sub {
  font-size: 24rpx;
  margin-top: 12rpx;
}

.store-list {
  padding: 0 24rpx;
}

.store-card {
  background: #fff;
  border-radius: 16rpx;
  padding: 32rpx;
  margin-bottom: 20rpx;
  display: flex;
  flex-direction: column;
}

.store-card:active {
  background: #fafafa;
}

.store-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 14rpx;
}

.store-name {
  font-size: 34rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.store-code {
  font-size: 24rpx;
  color: #b0b0b0;
}

.store-address {
  font-size: 26rpx;
  color: #666;
  line-height: 1.6;
}

.store-phone {
  font-size: 24rpx;
  color: #a0a0a0;
  margin-top: 8rpx;
}

.footer {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60rpx 40rpx 20rpx;
}

.link {
  font-size: 28rpx;
  color: #1f1f1f;
  padding: 16rpx 40rpx;
  border: 1rpx solid #e5e5e5;
  border-radius: 40rpx;
  background: #fff;
}

.version {
  font-size: 22rpx;
  color: #c0c0c0;
  margin-top: 32rpx;
}
</style>
