<template>
  <view class="page">
    <view v-if="storeId === null" class="blocked">
      <text class="blocked-title">先选一家门店</text>
      <text class="blocked-sub">
        代客点单必须知道是哪家店在点——价格、上架、限量都按门店算。
      </text>
    </view>

    <template v-else>
      <!-- 门店：服务员/收银员只有自己那家，不用选；总部账号（老板/运营）要选 -->
      <view v-if="canPickStore" class="store-bar">
        <picker
          mode="selector"
          :range="storeNames"
          :value="storeIndex"
          @change="switchStore"
        >
          <view class="store-picker">
            {{ storeName || '选择门店' }}
            <text class="caret">▾</text>
          </view>
        </picker>
      </view>

      <!-- 分类栏：横着滑。分类是从菜单里现推的，顺序由后端定死 -->
      <scroll-view class="cats" scroll-x>
        <view class="cat-row">
          <text
            class="cat"
            :class="{ active: activeCategory === null }"
            @tap="activeCategory = null"
          >
            全部
          </text>
          <text
            v-for="cat in categories"
            :key="cat.id"
            class="cat"
            :class="{ active: activeCategory === cat.id }"
            @tap="activeCategory = cat.id"
          >
            {{ cat.name }}
          </text>
        </view>
      </scroll-view>

      <view v-if="loading" class="hint">加载菜单中…</view>

      <scroll-view v-else class="dishes" scroll-y>
        <view
          v-for="dish in visibleDishes"
          :key="dish.dish_id"
          class="dish"
          @tap="pickDish(dish)"
        >
          <view class="dish-main">
            <text class="dish-name">{{ dish.name }}</text>
            <text class="dish-desc">{{ dish.description || ' ' }}</text>
          </view>
          <view class="dish-right">
            <text class="dish-price">{{ formatPrice(dish.price) }}</text>
            <text v-if="dish.option_groups.length" class="dish-tag">可选规格</text>
            <text v-if="countOf(dish.dish_id)" class="dish-count">
              ×{{ countOf(dish.dish_id) }}
            </text>
          </view>
        </view>
        <text v-if="visibleDishes.length === 0" class="hint">这个分类下暂时没有可点的菜</text>
      </scroll-view>

      <!-- 底部：购物车摘要 + 提交 -->
      <view class="cart-bar">
        <view class="cart-info" @tap="cartVisible = true">
          <text class="cart-count">已点 {{ cartCount }} 份</text>
          <text class="cart-total">{{ formatPrice(cartTotal) }}</text>
        </view>
        <button class="submit" :disabled="cartCount === 0 || submitting" @tap="handleSubmit">
          {{ submitting ? '提交中…' : '下单' }}
        </button>
      </view>
    </template>

    <!-- 规格选择弹层 -->
    <view v-if="picking" class="mask" @tap="picking = null">
      <view class="sheet" @tap.stop>
        <view class="sheet-head">
          <text class="sheet-title">{{ picking.name }}</text>
          <text class="sheet-sub">按份计价，加料的钱另算</text>
        </view>

        <scroll-view class="sheet-body" scroll-y>
          <view v-for="group in picking.option_groups" :key="group.name" class="group">
            <text class="group-name">
              {{ group.name }}
              <text v-if="group.is_required" class="required">必选</text>
              <text class="group-type">{{ group.selection_type === 'single' ? '单选' : '多选' }}</text>
            </text>

            <view class="options">
              <view
                v-for="option in group.options"
                :key="option.id"
                class="option"
                :class="{ on: chosen.includes(option.id) }"
                @tap="toggleOption(group, option)"
              >
                <text class="option-name">{{ option.name }}</text>
                <text v-if="option.extra_price" class="option-price">
                  +{{ formatPrice(option.extra_price) }}
                </text>
              </view>
            </view>
          </view>
        </scroll-view>

        <view class="sheet-foot">
          <view class="qty">
            <text class="qty-btn" @tap="pickedQty > 1 && pickedQty--">−</text>
            <text class="qty-value">{{ pickedQty }}</text>
            <text class="qty-btn" @tap="pickedQty++">＋</text>
          </view>
          <button class="sheet-add" @tap="confirmPick">
            加入 · {{ formatPrice(pickedUnitPrice * pickedQty) }}
          </button>
        </view>
      </view>
    </view>

    <!-- 购物车明细 -->
    <view v-if="cartVisible" class="mask" @tap="cartVisible = false">
      <view class="sheet cart-sheet" @tap.stop>
        <view class="sheet-head">
          <text class="sheet-title">已点 {{ cartCount }} 份</text>
          <text class="clear" @tap="handleClear">清空</text>
        </view>

        <scroll-view class="sheet-body" scroll-y>
          <view v-for="item in cartState.items" :key="item.key" class="cart-item">
            <view class="cart-line">
              <text class="cart-name">
                {{ item.name }}
                <text v-if="item.options_text" class="cart-options">{{ item.options_text }}</text>
              </text>
              <text class="cart-remove" @tap="removeItem(item)">×</text>
            </view>
            <view class="cart-line">
              <text class="cart-price">{{ formatPrice(item.unit_price) }}</text>
              <view class="qty">
                <text class="qty-btn" @tap="changeQuantity(item, -1)">−</text>
                <text class="qty-value">{{ item.quantity }}</text>
                <text class="qty-btn" @tap="changeQuantity(item, 1)">＋</text>
              </view>
              <text class="cart-subtotal">
                {{ formatPrice(item.unit_price * item.quantity) }}
              </text>
            </view>
          </view>
        </scroll-view>

        <view class="sheet-foot">
          <button class="sheet-add" @tap="cartVisible = false">继续点</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { createOrder } from '@/api/orders'
import { getStoreMenu } from '@/api/menu'
import type { DishOption, DishOptionGroup, StoreMenuRow, StoreOption } from '@/api/types'
import {
  addToCart,
  cartCount,
  cartState,
  cartTotal,
  changeQuantity,
  clearCart,
  removeItem,
} from '@/stores/cart'
import { getStoreOptions } from '@/api/stores'
import { hasPermission, myStoreId } from '@/stores/auth'
import { formatPrice } from '@/utils/format'

/**
 * 门店从哪来
 *
 * 有归属门店的（服务员/收银员/店长）直接用自己那家，不用选。
 * **总部账号（老板/运营）没有归属门店**，得在这儿挑一家——
 * 电脑上的点单页本来就有这个选择器，小程序端一开始漏了，
 * 结果是老板登进来只看到一句「用不了代客点单」。
 */
const storeId = ref<number | null>(myStoreId())
const stores = ref<StoreOption[]>([])
const canPickStore = computed(() => hasPermission('store:view'))

const storeNames = computed(() => stores.value.map((store) => store.name))
const storeIndex = computed(() =>
  Math.max(stores.value.findIndex((store) => store.id === storeId.value), 0)
)
const storeName = computed(() =>
  stores.value.find((store) => store.id === storeId.value)?.name ?? ''
)

async function loadStores() {
  if (!canPickStore.value) return
  try {
    stores.value = (await getStoreOptions()).stores
    // 没归属门店时默认挑第一家——让老板先看到菜，比让他先做一道选择题好。
    // **不记到本地**：老板代客点单是偶发的事，记着反而容易在下一单点错店
    if (storeId.value === null && stores.value.length) {
      storeId.value = stores.value[0].id
    }
  } catch {
    // request.ts 已经弹了提示
  }
}

function switchStore(event: { detail: { value: number } }) {
  const picked = stores.value[event.detail.value]
  if (!picked || picked.id === storeId.value) return
  storeId.value = picked.id
  loadMenu()
}
const dishes = ref<StoreMenuRow[]>([])
const loading = ref(false)
const submitting = ref(false)
const activeCategory = ref<number | null>(null)
const cartVisible = ref(false)

const categories = computed(() => {
  // 分类从菜品里现推，避免多一次请求。**顺序就是后端给的顺序**——
  // 后端已经按 Category.sort_order 排过了，这里再用 Map 保证「首次出现的位置」
  const seen = new Map<number, string>()
  for (const dish of dishes.value) {
    if (!seen.has(dish.category_id)) seen.set(dish.category_id, dish.category_name || '未分类')
  }
  return [...seen.entries()].map(([id, name]) => ({ id, name }))
})

const visibleDishes = computed(() =>
  activeCategory.value === null
    ? dishes.value
    : dishes.value.filter((dish) => dish.category_id === activeCategory.value)
)

/** 这道菜已经点了几份——卡片右上角那个小数字 */
function countOf(dishId: number): number {
  return cartState.items
    .filter((item) => item.dish_id === dishId)
    .reduce((sum, item) => sum + item.quantity, 0)
}

async function loadMenu() {
  if (storeId.value === null) return
  loading.value = true
  try {
    const data = await getStoreMenu(storeId.value)
    // 本店下架的菜不显示——点单界面上摆着点不了的菜只会添乱
    dishes.value = data.dishes.filter((dish) => dish.is_available)
    activeCategory.value = null
  } catch {
    // request.ts 已经弹了提示
  } finally {
    loading.value = false
  }
}

// ---------- 规格选择 ----------

const picking = ref<StoreMenuRow | null>(null)
const chosen = ref<number[]>([])
const pickedQty = ref(1)

/** 选中的规格一共要加多少钱——单价 = 本店价 + 各选项加价 */
const pickedUnitPrice = computed(() => {
  if (!picking.value) return 0
  let price = picking.value.price
  for (const group of picking.value.option_groups) {
    for (const option of group.options) {
      if (chosen.value.includes(option.id)) price += option.extra_price
    }
  }
  return price
})

function pickDish(dish: StoreMenuRow) {
  // 没有规格的菜直接进购物车，少一次弹窗
  if (dish.option_groups.length === 0) {
    addToCart({
      dish_id: dish.dish_id,
      name: dish.name,
      unit_price: dish.price,
      quantity: 1,
      option_ids: [],
      options_text: '',
    })
    uni.showToast({ title: `已加 ${dish.name}`, icon: 'none', duration: 800 })
    return
  }

  picking.value = dish
  chosen.value = []
  pickedQty.value = 1
  // 必选的单选组默认选第一个：不选提交不了，让收银员多点一次没意义
  for (const group of dish.option_groups) {
    if (group.is_required && group.selection_type === 'single' && group.options.length) {
      chosen.value.push(group.options[0].id)
    }
  }
}

function toggleOption(group: DishOptionGroup, option: DishOption) {
  if (group.selection_type === 'single') {
    // 单选：把同组的其他选项挤掉
    const siblings = group.options.map((item) => item.id)
    chosen.value = chosen.value.filter((id) => !siblings.includes(id))
    chosen.value.push(option.id)
    return
  }
  // 多选：再点一下取消。**加料可以加多份**（加两个蛋），
  // 那是点两次「加蛋」——同一行数量 +1，走的是购物车那边
  chosen.value = chosen.value.includes(option.id)
    ? chosen.value.filter((id) => id !== option.id)
    : [...chosen.value, option.id]
}

function confirmPick() {
  const dish = picking.value
  if (!dish) return

  // 必选组漏选了——后端也会拦（`build_order_item`），但在这儿拦住体验好得多：
  // 不用等一次往返，也不用对着一个 400 猜是哪一组没选
  for (const group of dish.option_groups) {
    if (group.is_required && !group.options.some((option) => chosen.value.includes(option.id))) {
      uni.showToast({ title: `「${group.name}」要选一个`, icon: 'none' })
      return
    }
  }

  const names = dish.option_groups.flatMap((group) =>
    group.options.filter((option) => chosen.value.includes(option.id)).map((option) => option.name)
  )

  addToCart({
    dish_id: dish.dish_id,
    name: dish.name,
    unit_price: pickedUnitPrice.value,
    quantity: pickedQty.value,
    option_ids: [...chosen.value],
    options_text: names.join(' / '),
  })

  picking.value = null
}

// ---------- 提交 ----------

function handleClear() {
  uni.showModal({
    title: '清空点单',
    content: '购物车里还有没提交的菜，确定要清空吗？',
    success: (res) => {
      if (!res.confirm) return
      clearCart()
      cartVisible.value = false
    },
  })
}

async function handleSubmit() {
  if (storeId.value === null || cartCount.value === 0 || submitting.value) return

  submitting.value = true
  try {
    // **只传菜品和数量，不传价格**——后端会按本店实际价重算一遍。
    // 前端报的价一律不算数，这是收银系统最基本的要求
    const order = await createOrder({
      store_id: storeId.value,
      source: 'dine_in',
      items: cartState.items.map((item) => ({
        dish_id: item.dish_id,
        quantity: item.quantity,
        option_ids: item.option_ids,
      })),
    })

    clearCart()
    cartVisible.value = false

    uni.showModal({
      title: '下单成功',
      content: `单号 ${order.order_no}\n应付 ${formatPrice(order.payable_amount)}`,
      confirmText: '去看订单',
      cancelText: '继续点',
      success: (res) => {
        if (res.confirm) uni.navigateTo({ url: '/pages/order/list' })
      },
    })
  } catch {
    // request.ts 已经弹了提示（必选规格没选、本店已下架等后端也会再校验一遍）
  } finally {
    submitting.value = false
  }
}

onLoad(async () => {
  await loadStores()
  loadMenu()
})
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f5f5f5;
  box-sizing: border-box;
}

.blocked {
  margin: 80rpx 32rpx;
  padding: 48rpx 32rpx;
  background: #fff;
  border-radius: 20rpx;
}

.blocked-title {
  display: block;
  font-size: 34rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.blocked-sub {
  display: block;
  margin-top: 16rpx;
  font-size: 26rpx;
  color: #a0a0a0;
  line-height: 1.7;
}

.store-bar {
  flex-shrink: 0;
  padding: 20rpx 24rpx 4rpx;
  background: #fff;
}

.store-picker {
  display: inline-flex;
  align-items: center;
  font-size: 30rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.caret {
  margin-left: 8rpx;
  font-size: 22rpx;
  color: #8a8a8a;
}

.cats {
  flex-shrink: 0;
  background: #fff;
  white-space: nowrap;
}

.cat-row {
  display: inline-flex;
  padding: 20rpx 24rpx;
}

.cat {
  padding: 12rpx 28rpx;
  margin-right: 16rpx;
  border-radius: 32rpx;
  font-size: 26rpx;
  color: #1f1f1f;
  background: #f2f2f2;
  /* 分类栏是横向滚动的，**不能让它们被挤窄**——不写这条的话
     六个分类会一起挤进屏幕宽度，「商务套餐」会折成两行（实测过） */
  flex-shrink: 0;
  white-space: nowrap;
}

.cat.active {
  background: #1f1f1f;
  color: #fff;
}

.dishes {
  flex: 1;
  padding: 20rpx 24rpx;
  box-sizing: border-box;
}

.dish {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 28rpx;
  margin-bottom: 16rpx;
  background: #fff;
  border-radius: 16rpx;
}

.dish:active {
  background: #f0f0f0;
}

.dish-main {
  flex: 1;
  min-width: 0;
}

.dish-name {
  display: block;
  font-size: 30rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.dish-desc {
  display: block;
  margin-top: 8rpx;
  font-size: 24rpx;
  color: #a0a0a0;
}

.dish-right {
  text-align: right;
  flex-shrink: 0;
  margin-left: 20rpx;
}

.dish-price {
  display: block;
  font-size: 32rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.dish-tag {
  display: block;
  margin-top: 8rpx;
  font-size: 22rpx;
  color: #8a8a8a;
}

.dish-count {
  display: block;
  margin-top: 6rpx;
  font-size: 24rpx;
  color: #c45656;
}

.hint {
  display: block;
  padding: 80rpx 0;
  text-align: center;
  font-size: 26rpx;
  color: #a0a0a0;
}

.cart-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  padding: 20rpx 24rpx;
  background: #fff;
  border-top: 1px solid #e8e8e8;
}

.cart-info {
  flex: 1;
}

.cart-count {
  display: block;
  font-size: 24rpx;
  color: #8a8a8a;
}

.cart-total {
  display: block;
  font-size: 38rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.submit {
  width: 220rpx;
  height: 84rpx;
  line-height: 84rpx;
  background: #1f1f1f;
  color: #fff;
  font-size: 30rpx;
  border-radius: 12rpx;
}

.submit[disabled] {
  background: #c0c0c0;
}

/* ---------- 弹层 ---------- */

.mask {
  position: fixed;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: flex-end;
  z-index: 10;
}

.sheet {
  width: 100%;
  max-height: 80vh;
  background: #fff;
  border-radius: 24rpx 24rpx 0 0;
  display: flex;
  flex-direction: column;
}

.sheet-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 32rpx;
  border-bottom: 1px solid #f0f0f0;
}

.sheet-title {
  font-size: 32rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.sheet-sub {
  font-size: 24rpx;
  color: #a0a0a0;
}

.sheet-body {
  flex: 1;
  max-height: 56vh;
  padding: 24rpx 32rpx;
  box-sizing: border-box;
}

.sheet-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx 32rpx;
  border-top: 1px solid #f0f0f0;
}

.group {
  margin-bottom: 36rpx;
}

.group-name {
  display: block;
  font-size: 28rpx;
  color: #1f1f1f;
  margin-bottom: 16rpx;
}

.required {
  margin-left: 8rpx;
  font-size: 22rpx;
  color: #c45656;
}

.group-type {
  margin-left: 8rpx;
  font-size: 22rpx;
  color: #b0b0b0;
}

.options {
  display: flex;
  flex-wrap: wrap;
}

.option {
  padding: 14rpx 28rpx;
  margin: 0 16rpx 16rpx 0;
  border: 1px solid #e0e0e0;
  border-radius: 32rpx;
  font-size: 26rpx;
  color: #1f1f1f;
}

.option.on {
  border-color: #1f1f1f;
  background: #1f1f1f;
  color: #fff;
}

.option-price {
  margin-left: 8rpx;
  font-size: 22rpx;
}

.qty {
  display: flex;
  align-items: center;
}

.qty-btn {
  width: 60rpx;
  height: 60rpx;
  line-height: 56rpx;
  text-align: center;
  border: 1px solid #e0e0e0;
  border-radius: 50%;
  font-size: 32rpx;
  color: #1f1f1f;
}

.qty-value {
  min-width: 60rpx;
  text-align: center;
  font-size: 30rpx;
}

.sheet-add {
  flex: 1;
  margin-left: 24rpx;
  height: 84rpx;
  line-height: 84rpx;
  background: #1f1f1f;
  color: #fff;
  font-size: 28rpx;
  border-radius: 12rpx;
}

.cart-sheet .sheet-body {
  max-height: 50vh;
}

.cart-item {
  padding: 24rpx 0;
  border-bottom: 1px dashed #eee;
}

.cart-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.cart-name {
  flex: 1;
  font-size: 28rpx;
  color: #1f1f1f;
}

.cart-options {
  margin-left: 8rpx;
  font-size: 24rpx;
  color: #8a8a8a;
}

.cart-remove {
  padding: 0 12rpx;
  font-size: 34rpx;
  color: #a0a0a0;
}

.cart-price {
  font-size: 24rpx;
  color: #8a8a8a;
}

.cart-subtotal {
  min-width: 120rpx;
  text-align: right;
  font-size: 28rpx;
  font-weight: 600;
  color: #1f1f1f;
}

.clear {
  font-size: 26rpx;
  color: #c45656;
}
</style>