<template>
  <view class="page">
    <!-- 门店 + 分类 -->
    <view class="topbar">
      <text class="store-name">{{ storeName }}</text>
      <text class="my-orders" @tap="goMyOrders">我的订单 ›</text>
    </view>

    <!-- 搜索：和分类是两个独立的筛子，同时生效 -->
    <view class="search-row">
      <input
        v-model="search"
        class="search-input"
        type="text"
        placeholder="搜索菜品"
        confirm-type="search"
      />
      <text v-if="search" class="search-clear" @tap="search = ''">✕</text>
    </view>

    <scroll-view class="category-bar" scroll-x :show-scrollbar="false">
      <view class="category-row">
        <text
          class="category"
          :class="{ active: activeCategory === null }"
          @tap="activeCategory = null"
        >
          全部
        </text>
        <text
          v-for="category in categories"
          :key="category.id"
          class="category"
          :class="{ active: activeCategory === category.id }"
          @tap="activeCategory = category.id"
        >
          {{ category.name }}
        </text>
      </view>
    </scroll-view>

    <!-- 菜品 -->
    <scroll-view class="dish-scroll" scroll-y>
      <!-- 空列表的提示是动态的：搜不到时要说明是在哪个分类里没搜到，
           不然用户不知道分类还在筛 -->
      <view v-if="loading" class="hint">加载中…</view>
      <view v-else-if="visibleDishes.length === 0" class="hint">{{ emptyHint }}</view>
      <view v-else class="dish-list">
        <view
          v-for="dish in visibleDishes"
          :key="dish.dish_id"
          class="dish-card"
          @tap="pickDish(dish)"
        >
          <view class="dish-main">
            <text class="dish-name">{{ dish.name }}</text>
            <text v-if="dish.description" class="dish-desc">{{ dish.description }}</text>
            <view class="dish-bottom">
              <text class="dish-price">{{ formatPrice(dish.price) }}</text>
              <text v-if="dish.option_groups.length" class="dish-tag">可选规格</text>
            </view>
          </view>
          <view class="dish-add">＋</view>
        </view>
        <view class="scroll-bottom-space"></view>
      </view>
    </scroll-view>

    <!-- 底部购物车栏 -->
    <view class="cart-bar" :class="{ empty: cartCount === 0 }">
      <view class="cart-left" @tap="cartCount > 0 && (cartVisible = true)">
        <view class="cart-badge" v-if="cartCount > 0">{{ cartCount }}</view>
        <view class="cart-badge placeholder" v-else>0</view>
        <text class="cart-total">{{ formatPrice(cartTotal) }}</text>
      </view>
      <view
        class="cart-action"
        :class="{ disabled: cartCount === 0 }"
        @tap="cartCount > 0 && (cartVisible = true)"
      >
        去结算
      </view>
    </view>

    <!-- 购物车弹层 -->
    <view v-if="cartVisible" class="mask" @tap="cartVisible = false">
      <view class="sheet" @tap.stop>
        <view class="sheet-head">
          <text>已点 {{ cartCount }} 份</text>
          <text class="clear" @tap="handleClear">清空</text>
        </view>

        <scroll-view class="sheet-list" scroll-y>
          <view v-for="item in cart.items" :key="item.key" class="cart-item">
            <view class="cart-item-main">
              <text class="cart-item-name">{{ item.name }}</text>
              <text v-if="item.options_text" class="cart-item-options">{{ item.options_text }}</text>
            </view>
            <text class="cart-item-price">{{ formatPrice(item.unit_price) }}</text>
            <view class="qty">
              <text class="qty-btn" @tap="changeQuantity(item, -1)">−</text>
              <text class="qty-value">{{ item.quantity }}</text>
              <text class="qty-btn" @tap="changeQuantity(item, 1)">＋</text>
            </view>
          </view>
        </scroll-view>

        <view class="sheet-form">
          <view class="source-row">
            <text
              v-for="option in SOURCE_OPTIONS"
              :key="option.value"
              class="source"
              :class="{ active: cart.source === option.value }"
              @tap="cart.source = option.value"
            >
              {{ option.label }}
            </text>
          </view>
          <input v-model="cart.remark" class="remark-input" placeholder="备注（少辣、不要香菜…）" />
        </view>

        <view class="sheet-foot">
          <text class="sheet-total">合计 {{ formatPrice(cartTotal) }}</text>
          <view class="submit" :class="{ disabled: submitting }" @tap="handleSubmit">
            {{ submitting ? '提交中…' : '提交订单' }}
          </view>
        </view>
      </view>
    </view>

    <!-- 规格选择弹层 -->
    <view v-if="pickingDish" class="mask" @tap="pickingDish = null">
      <view class="sheet" @tap.stop>
        <view class="sheet-head">
          <view class="picker-title">
            <text class="picker-name">{{ pickingDish.name }}</text>
            <text v-if="pickingDish.description" class="picker-desc">
              {{ pickingDish.description }}
            </text>
          </view>
        </view>

        <scroll-view class="sheet-list" scroll-y>
          <view v-for="group in pickingDish.option_groups" :key="group.id" class="group">
            <view class="group-head">
              <text class="group-name">{{ group.name }}</text>
              <text v-if="group.is_required" class="required">必选</text>
              <text class="group-type">{{ group.selection_type_label }}</text>
            </view>
            <view class="option-row">
              <text
                v-for="option in group.options"
                :key="option.id"
                class="option"
                :class="{ active: isChosen(group.id, option.id) }"
                @tap="toggleOption(group, option.id)"
              >
                {{ option.name }}<text v-if="option.extra_price > 0" class="extra">
                  +{{ option.extra_price }}</text>
              </text>
            </view>
          </view>
        </scroll-view>

        <view class="sheet-foot">
          <view class="qty picker-qty">
            <text class="qty-btn" @tap="changePickQuantity(-1)">−</text>
            <text class="qty-value">{{ pickQuantity }}</text>
            <text class="qty-btn" @tap="changePickQuantity(1)">＋</text>
          </view>
          <view class="submit" @tap="confirmPick">
            加入 · {{ formatPrice(pickUnitPrice * pickQuantity) }}
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { createOrder, getMenu } from '@/api/public'
import type { DishOptionGroup, MenuRow } from '@/api/types'
import { addToCart, cart, cartCount, cartTotal, changeQuantity, clearCart } from '@/stores/cart'
import { saveOrder } from '@/stores/myOrders'
import { formatPrice } from '@/utils/format'

const SOURCE_OPTIONS = [
  { value: 'dine_in', label: '堂食' },
  { value: 'takeaway', label: '自取' },
  { value: 'delivery', label: '外卖' },
]

const storeId = ref(0)
const storeName = ref('')
const dishes = ref<MenuRow[]>([])
const loading = ref(true)
const activeCategory = ref<number | null>(null)
const search = ref('')
const cartVisible = ref(false)
const submitting = ref(false)

/** 分类从菜品里现推，只展示真的上了菜的分类 */
const categories = computed(() => {
  const seen = new Map<number, string>()
  for (const dish of dishes.value) {
    if (!seen.has(dish.category_id)) seen.set(dish.category_id, dish.category_name || '未分类')
  }
  return [...seen.entries()].map(([id, name]) => ({ id, name }))
})

const visibleDishes = computed(() => {
  const keyword = search.value.trim()
  return dishes.value.filter((dish) => {
    if (activeCategory.value !== null && dish.category_id !== activeCategory.value) return false
    // 只匹配菜名，不匹配描述——搜「辣」出来一堆不辣的菜更让人迷惑
    if (keyword && !dish.name.includes(keyword)) return false
    return true
  })
})

/** 列表空了要说清为什么：是这家店没菜，还是搜索＋分类筛没了 */
const emptyHint = computed(() => {
  const keyword = search.value.trim()
  if (!keyword) return '没有可点的菜'
  const category = categories.value.find((item) => item.id === activeCategory.value)
  return category
    ? `「${category.name}」里没找到「${keyword}」，试试其他分类`
    : `没找到「${keyword}」`
})

// ---------- 规格选择 ----------

const pickingDish = ref<MenuRow | null>(null)
const pickQuantity = ref(1)
/** 组 id → 选中的选项 id */
const picked = reactive<Record<number, number[]>>({})

const pickUnitPrice = computed(() => {
  const dish = pickingDish.value
  if (!dish) return 0
  let price = dish.price
  for (const group of dish.option_groups) {
    const chosen = picked[group.id] || []
    for (const option of group.options) {
      if (chosen.includes(option.id)) price += option.extra_price
    }
  }
  return price
})

/** 按规格组的顺序铺平选中的选项 */
const pickOptions = computed(() => {
  const dish = pickingDish.value
  if (!dish) return [] as { id: number; name: string }[]
  const result: { id: number; name: string }[] = []
  for (const group of dish.option_groups) {
    const chosen = picked[group.id] || []
    for (const option of group.options) {
      if (chosen.includes(option.id)) result.push({ id: option.id, name: option.name })
    }
  }
  return result
})

function isChosen(groupId: number, optionId: number): boolean {
  return (picked[groupId] || []).includes(optionId)
}

function toggleOption(group: DishOptionGroup, optionId: number) {
  const chosen = picked[group.id] || []
  if (group.selection_type === 'single') {
    // 单选组：点了就换成它
    picked[group.id] = [optionId]
    return
  }
  // 多选组：再点一次取消
  picked[group.id] = chosen.includes(optionId)
    ? chosen.filter((id) => id !== optionId)
    : [...chosen, optionId]
}

function changePickQuantity(delta: number) {
  const next = pickQuantity.value + delta
  if (next < 1 || next > 99) return
  pickQuantity.value = next
}

function pickDish(dish: MenuRow) {
  // 没有规格的菜直接进购物车，少一次弹层
  if (dish.option_groups.length === 0) {
    addToCart({
      dish_id: dish.dish_id, name: dish.name, unit_price: dish.price,
      quantity: 1, option_ids: [], options_text: '',
    })
    uni.showToast({ title: '已加入', icon: 'none', duration: 800 })
    return
  }

  pickingDish.value = dish
  pickQuantity.value = 1
  for (const key of Object.keys(picked)) delete picked[Number(key)]
  // 必选组默认选第一个——顾客少点一下，多数人也是选标准份
  for (const group of dish.option_groups) {
    picked[group.id] = group.is_required && group.options.length ? [group.options[0].id] : []
  }
}

function confirmPick() {
  const dish = pickingDish.value
  if (!dish) return

  // 和后端同样的校验，错了当场提示，别等提交才吃 400
  for (const group of dish.option_groups) {
    if (group.is_required && (picked[group.id] || []).length === 0) {
      uni.showToast({ title: `请选择「${group.name}」`, icon: 'none' })
      return
    }
  }

  addToCart({
    dish_id: dish.dish_id,
    name: dish.name,
    unit_price: pickUnitPrice.value,
    quantity: pickQuantity.value,
    option_ids: pickOptions.value.map((option) => option.id),
    options_text: pickOptions.value.map((option) => option.name).join(','),
  })
  pickingDish.value = null
  uni.showToast({ title: '已加入', icon: 'none', duration: 800 })
}

// ---------- 结算 ----------

function handleClear() {
  clearCart()
  cartVisible.value = false
}

async function handleSubmit() {
  if (submitting.value) return
  if (cart.items.length === 0) return

  submitting.value = true
  try {
    // 只传菜品和数量，**不传价格**——后端会按本店实际价重算一遍
    const order = await createOrder({
      store_id: storeId.value,
      source: cart.source,
      remark: cart.remark,
      items: cart.items.map((item) => ({
        dish_id: item.dish_id,
        quantity: item.quantity,
        option_ids: item.option_ids,
      })),
    })
    saveOrder(order)
    clearCart()
    cartVisible.value = false
    uni.redirectTo({
      url: `/pages/order/detail?orderNo=${order.order_no}&token=${order.query_token}`,
    })
  } catch {
    // request.ts 已经弹了提示（必选规格没选、菜品已下架等后端也会再校验一遍）
  } finally {
    submitting.value = false
  }
}

function goMyOrders() {
  uni.navigateTo({ url: '/pages/orders/orders' })
}

async function loadMenu() {
  loading.value = true
  try {
    const data = await getMenu(storeId.value)
    dishes.value = data.dishes
  } catch {
    // request.ts 已经弹了提示
  } finally {
    loading.value = false
  }
}

onLoad((query) => {
  storeId.value = Number(query?.storeId || 0)
  storeName.value = decodeURIComponent(query?.storeName || '')
  // 换了门店就清空购物车：在 A 店点的菜到了 B 店可能没有、价格也不一样
  if (cart.storeId !== storeId.value) {
    clearCart()
    cart.storeId = storeId.value
    cart.storeName = storeName.value
  }
  loadMenu()
})
</script>

<style scoped>
.page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20rpx 32rpx;
  background: #fff;
}

.store-name {
  font-size: 32rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.my-orders {
  font-size: 26rpx;
  color: #8a8a8a;
}

.search-row {
  display: flex;
  align-items: center;
  padding: 0 32rpx 20rpx;
  background: #fff;
}

.search-input {
  flex: 1;
  height: 64rpx;
  background: #f5f5f5;
  border-radius: 32rpx;
  padding: 0 28rpx;
  font-size: 26rpx;
}

.search-clear {
  margin-left: 16rpx;
  padding: 8rpx 12rpx;
  font-size: 28rpx;
  color: #8a8a8a;
}

.category-bar {
  background: #fff;
  white-space: nowrap;
  padding-bottom: 16rpx;
}

.category-row {
  display: inline-flex;
  padding: 0 24rpx;
}

.category {
  display: inline-block;
  padding: 10rpx 28rpx;
  margin-right: 16rpx;
  border-radius: 32rpx;
  font-size: 26rpx;
  background: #f2f2f2;
  color: #1f1f1f;
}

.category.active {
  background: #1f1f1f;
  color: #fff;
}

.dish-scroll {
  flex: 1;
  min-height: 0;
}

.dish-list {
  padding: 20rpx 24rpx 0;
}

.dish-card {
  background: #fff;
  border-radius: 16rpx;
  padding: 28rpx;
  margin-bottom: 16rpx;
  display: flex;
  align-items: center;
}

.dish-card:active {
  background: #fafafa;
}

.dish-main {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.dish-name {
  font-size: 30rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.dish-desc {
  font-size: 24rpx;
  color: #a0a0a0;
  margin-top: 8rpx;
}

.dish-bottom {
  display: flex;
  align-items: center;
  margin-top: 16rpx;
}

.dish-price {
  font-size: 32rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.dish-tag {
  font-size: 22rpx;
  color: #8a8a8a;
  border: 1rpx solid #e0e0e0;
  border-radius: 6rpx;
  padding: 2rpx 10rpx;
  margin-left: 16rpx;
}

.dish-add {
  width: 56rpx;
  height: 56rpx;
  border-radius: 50%;
  background: #1f1f1f;
  color: #fff;
  font-size: 36rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.scroll-bottom-space {
  height: 160rpx;
}

.hint {
  padding: 120rpx 40rpx;
  text-align: center;
  font-size: 28rpx;
  color: #a0a0a0;
}

/* ---------- 底部购物车栏 ---------- */

.cart-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  height: 110rpx;
  background: #1f1f1f;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32rpx;
  padding-bottom: env(safe-area-inset-bottom);
}

.cart-left {
  display: flex;
  align-items: center;
}

.cart-badge {
  min-width: 44rpx;
  height: 44rpx;
  border-radius: 22rpx;
  background: #fff;
  color: #1f1f1f;
  font-size: 24rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 12rpx;
}

.cart-badge.placeholder {
  background: #4a4a4a;
  color: #9a9a9a;
}

.cart-total {
  color: #fff;
  font-size: 34rpx;
  font-weight: 600;
  margin-left: 24rpx;
}

.cart-action {
  color: #1f1f1f;
  background: #fff;
  font-size: 28rpx;
  padding: 16rpx 44rpx;
  border-radius: 40rpx;
}

.cart-action.disabled {
  background: #4a4a4a;
  color: #9a9a9a;
}

/* ---------- 弹层 ---------- */

.mask {
  position: fixed;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: flex-end;
  z-index: 100;
}

.sheet {
  width: 100%;
  background: #fff;
  border-radius: 24rpx 24rpx 0 0;
  padding-bottom: env(safe-area-inset-bottom);
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}

.sheet-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 28rpx 32rpx;
  border-bottom: 1rpx solid #f0f0f0;
  font-size: 28rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.clear {
  font-size: 26rpx;
  font-weight: 400;
  color: #8a8a8a;
}

.sheet-list {
  max-height: 46vh;
  padding: 0 32rpx;
}

.cart-item {
  display: flex;
  align-items: center;
  padding: 24rpx 0;
  border-bottom: 1rpx solid #f5f5f5;
}

.cart-item-main {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.cart-item-name {
  font-size: 28rpx;
  color: #1f1f1f;
}

.cart-item-options {
  font-size: 22rpx;
  color: #a0a0a0;
  margin-top: 6rpx;
}

.cart-item-price {
  font-size: 28rpx;
  color: #1f1f1f;
  margin-right: 24rpx;
}

.qty {
  display: flex;
  align-items: center;
}

.qty-btn {
  width: 52rpx;
  height: 52rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32rpx;
  color: #1f1f1f;
  border: 1rpx solid #e5e5e5;
  border-radius: 50%;
}

.qty-value {
  min-width: 56rpx;
  text-align: center;
  font-size: 28rpx;
}

.sheet-form {
  padding: 24rpx 32rpx 0;
}

.source-row {
  display: flex;
}

.source {
  padding: 12rpx 32rpx;
  margin-right: 16rpx;
  border-radius: 32rpx;
  font-size: 26rpx;
  background: #f2f2f2;
  color: #1f1f1f;
}

.source.active {
  background: #1f1f1f;
  color: #fff;
}

.remark-input {
  margin-top: 20rpx;
  height: 80rpx;
  background: #f7f7f7;
  border-radius: 12rpx;
  padding: 0 24rpx;
  font-size: 26rpx;
}

.sheet-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 28rpx 32rpx;
  border-top: 1rpx solid #f0f0f0;
  margin-top: 24rpx;
}

.sheet-total {
  font-size: 32rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.submit {
  background: #1f1f1f;
  color: #fff;
  font-size: 28rpx;
  padding: 18rpx 48rpx;
  border-radius: 40rpx;
}

.submit.disabled {
  background: #9a9a9a;
}

/* ---------- 规格选择 ---------- */

.picker-title {
  display: flex;
  flex-direction: column;
}

.picker-name {
  font-size: 32rpx;
}

.picker-desc {
  font-size: 24rpx;
  font-weight: 400;
  color: #a0a0a0;
  margin-top: 8rpx;
}

.group {
  padding: 28rpx 0 4rpx;
}

.group-head {
  display: flex;
  align-items: center;
  margin-bottom: 18rpx;
}

.group-name {
  font-size: 28rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.required {
  font-size: 22rpx;
  color: #c45656;
  margin-left: 12rpx;
}

.group-type {
  font-size: 22rpx;
  color: #b0b0b0;
  margin-left: 12rpx;
}

.option-row {
  display: flex;
  flex-wrap: wrap;
}

.option {
  padding: 14rpx 32rpx;
  margin: 0 16rpx 16rpx 0;
  border-radius: 32rpx;
  font-size: 26rpx;
  background: #f2f2f2;
  color: #1f1f1f;
}

.option.active {
  background: #1f1f1f;
  color: #fff;
}

.extra {
  color: #c45656;
  font-size: 22rpx;
}

.option.active .extra {
  color: #ffb0b0;
}

.picker-qty {
  gap: 8rpx;
}
</style>
