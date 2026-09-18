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
      <view class="cart-left" @tap="openCart">
        <view class="cart-badge" v-if="cartCount > 0">{{ cartCount }}</view>
        <view class="cart-badge placeholder" v-else>0</view>
        <text class="cart-total">{{ formatPrice(cartTotal) }}</text>
      </view>
      <view
        class="cart-action"
        :class="{ disabled: cartCount === 0 }"
        @tap="openCart"
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

        <!-- 用券：券挂在会员头上，所以没登录时这里不是"没有券"而是"登录后才有" -->
        <view v-if="!loggedIn" class="coupon-login" @tap="goLogin">
          <text class="coupon-login-text">登录后可用券</text>
          <text class="coupon-arrow">›</text>
        </view>
        <view v-else class="coupon-box">
          <view class="coupon-head">
            <text class="coupon-title">优惠券</text>
            <text v-if="couponLoading" class="coupon-hint">加载中…</text>
            <text v-else-if="!usableCoupons.length" class="coupon-hint">这单没有可用的券</text>
          </view>
          <view
            v-for="coupon in usableCoupons"
            :key="coupon.id"
            class="coupon-item"
            :class="{ active: selectedCoupon?.id === coupon.id }"
            @tap="pickCoupon(coupon)"
          >
            <text class="coupon-name">{{ coupon.template_name }}</text>
            <text class="coupon-value">−{{ formatPrice(coupon.discount) }}</text>
          </view>
        </view>

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
          <view class="foot-total">
            <text class="sheet-total">合计 {{ formatPrice(payableTotal) }}</text>
            <!-- 用了券才显示原价，不然这个数字反而让人以为没算对 -->
            <text v-if="selectedCoupon" class="sheet-origin">
              原价 {{ formatPrice(cartTotal) }}
            </text>
          </view>
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
              <!-- 加料能加多份，但光看界面看不出「点几下 = 几份」，提示一句 -->
              <text v-if="group.selection_type === 'multiple'" class="group-hint">
                连点可加多份
              </text>
            </view>
            <view class="option-row">
              <view
                v-for="option in group.options"
                :key="option.id"
                class="option"
                :class="{ active: countOf(group.id, option.id) > 0 }"
              >
                <!-- 减号只在多选组、且已选中时出现；减到 0 就是取消 -->
                <text
                  v-if="group.selection_type === 'multiple' && countOf(group.id, option.id) > 0"
                  class="opt-btn"
                  @tap.stop="removeOption(group, option.id)"
                >−</text>
                <text class="opt-label" @tap="addOption(group, option.id)">
                  {{ option.name }}<text v-if="option.extra_price > 0" class="extra">
                    +{{ option.extra_price }}</text>
                  <text v-if="countOf(group.id, option.id) > 1" class="opt-count">
                    ×{{ countOf(group.id, option.id) }}</text>
                </text>
              </view>
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
import { computed, reactive, ref, watch } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getUsableCoupons } from '@/api/member'
import { createOrder, getMenu } from '@/api/public'
import type { DishOptionGroup, MenuRow, UsableCoupon } from '@/api/types'
import { addToCart, cart, cartCount, cartTotal, changeQuantity, clearCart } from '@/stores/cart'
import { isLoggedIn } from '@/stores/memberAuth'
import { currentStoreId, storeState } from '@/stores/currentStore'
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

/** 这单能用的券。没登录时恒为空——券挂在会员头上，不登录就没有「谁的券」 */
const usableCoupons = ref<UsableCoupon[]>([])
const selectedCoupon = ref<UsableCoupon | null>(null)
const couponLoading = ref(false)
const loggedIn = ref(false)

/** 抵扣之后的应付。券抵的那部分由后端算，前端只做减法 */
const payableTotal = computed(() =>
  Math.max(0, cartTotal.value - (selectedCoupon.value?.discount ?? 0))
)

/**
 * 拉一次「这单能用的券」
 *
 * **打开弹层时拉，弹层里改了数量也重拉**：加一份菜可能就够着「满 50 减 10」了，
 * 减一份又不够了。门槛和适用门店这两条规则只在后端有，前端不猜。
 *
 * 重拉之后要拿新数据把选中那张**换成一条新的**——折扣率那种券的抵扣额
 * 是跟着金额走的（8.8 折：金额一变，减多少也变）。
 * 换的时候要是它已经不在可用列表里了（金额缩水、门槛不够了），就取消选中：
 * 留着的话提交会被后端拒掉，用户白填一遍还看不懂为什么。
 */
async function loadUsableCoupons() {
  loggedIn.value = isLoggedIn()
  if (!loggedIn.value) {
    usableCoupons.value = []
    selectedCoupon.value = null
    return
  }
  couponLoading.value = true
  try {
    const data = await getUsableCoupons(storeId.value, cartTotal.value)
    usableCoupons.value = data.coupons
    if (selectedCoupon.value) {
      selectedCoupon.value = data.coupons.find(
        (c) => c.id === selectedCoupon.value?.id
      ) ?? null
    }
  } catch {
    // 拉不到就当没有可用券：宁可让用户按原价下单，也不能把订单卡在这儿
    usableCoupons.value = []
    selectedCoupon.value = null
  } finally {
    couponLoading.value = false
  }
}

/** 再点一下已选中的那张 = 取消选它 */
function pickCoupon(coupon: UsableCoupon | null) {
  selectedCoupon.value = selectedCoupon.value?.id === coupon?.id ? null : coupon
}

function openCart() {
  if (cartCount.value === 0) return
  cartVisible.value = true
  loadUsableCoupons()
}

// 弹层开着的时候改数量：金额变了，能用的券跟着变
watch(cartTotal, () => {
  if (cartVisible.value) loadUsableCoupons()
})

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
/** 组 id → { 选项 id: 份数 }。加料可以加多份（加蛋 ×2） */
const picked = reactive<Record<number, Record<number, number>>>({})

/** 某个选项选了几份（0 = 没选） */
function countOf(groupId: number, optionId: number): number {
  return picked[groupId]?.[optionId] ?? 0
}

const pickUnitPrice = computed(() => {
  const dish = pickingDish.value
  if (!dish) return 0
  let price = dish.price
  for (const group of dish.option_groups) {
    for (const option of group.options) {
      price += option.extra_price * countOf(group.id, option.id)
    }
  }
  return price
})

/** 按规格组的顺序铺平选中的选项，带上份数 */
const pickOptions = computed(() => {
  const dish = pickingDish.value
  if (!dish) return [] as { id: number; name: string; count: number }[]
  const result: { id: number; name: string; count: number }[] = []
  for (const group of dish.option_groups) {
    for (const option of group.options) {
      const count = countOf(group.id, option.id)
      if (count > 0) result.push({ id: option.id, name: option.name, count })
    }
  }
  return result
})

/** 加一份。单选组是「换成它」——它只有选中/换一个两种状态，没有份数 */
function addOption(group: DishOptionGroup, optionId: number) {
  if (group.selection_type === 'single') {
    picked[group.id] = { [optionId]: 1 }
    return
  }
  const counts = picked[group.id] || (picked[group.id] = {})
  counts[optionId] = (counts[optionId] ?? 0) + 1
}

/** 减一份，减到 0 就是取消 */
function removeOption(group: DishOptionGroup, optionId: number) {
  const counts = picked[group.id]
  if (!counts) return
  const next = (counts[optionId] ?? 0) - 1
  if (next <= 0) delete counts[optionId]
  else counts[optionId] = next
}

/** 提交给后端的 option_ids：同一个 id 重复几次就是几份 */
const pickOptionIds = computed(() =>
  pickOptions.value.flatMap((option) => Array(option.count).fill(option.id))
)

const pickOptionsText = computed(() =>
  pickOptions.value
    .map((option) => (option.count > 1 ? `${option.name}×${option.count}` : option.name))
    .join(',')
)

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
    picked[group.id] = group.is_required && group.options.length
      ? { [group.options[0].id]: 1 }
      : {}
  }
}

function confirmPick() {
  const dish = pickingDish.value
  if (!dish) return

  // 和后端同样的校验，错了当场提示，别等提交才吃 400
  for (const group of dish.option_groups) {
    const anyPicked = group.options.some((option) => countOf(group.id, option.id) > 0)
    if (group.is_required && !anyPicked) {
      uni.showToast({ title: `请选择「${group.name}」`, icon: 'none' })
      return
    }
  }

  addToCart({
    dish_id: dish.dish_id,
    name: dish.name,
    unit_price: pickUnitPrice.value,
    quantity: pickQuantity.value,
    option_ids: pickOptionIds.value,
    options_text: pickOptionsText.value,
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
    // （券也一样：只传「用哪张」，抵多少是后端算的）
    const order = await createOrder({
      store_id: storeId.value,
      source: cart.source,
      remark: cart.remark,
      items: cart.items.map((item) => ({
        dish_id: item.dish_id,
        quantity: item.quantity,
        option_ids: item.option_ids,
      })),
      user_coupon_id: selectedCoupon.value?.id,
    })
    saveOrder(order)
    clearCart()
    selectedCoupon.value = null
    usableCoupons.value = []
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
  // 订单页现在是底部 tab 之一，**必须用 switchTab**（navigateTo 打不开 tab 页）
  uni.switchTab({ url: '/pages/orders/orders' })
}

/** 去登录页——登录页不是 tab，用 navigateTo（回来时这一页原样还在） */
function goLogin() {
  uni.navigateTo({ url: '/pages/login/login' })
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

/**
 * 门店从「当前门店」读，不从页面参数读
 *
 * 以前是「首页选店 → 带着 storeId 跳过来」，改成底部 tab 之后没有那次跳转了，
 * 门店存在本地（见 `stores/currentStore.ts`）。
 *
 * **用 onShow 不用 onLoad**：tab 页面切走再切回来不会重新 onLoad，
 * 但顾客可能刚在首页把门店换成了另一家——不重读的话，这一页还停在旧店的菜单上。
 */
onShow(() => {
  const id = currentStoreId()
  if (!id) {
    // 一家店都没选（正常进不来，首页会自动挑一家）——给个提示，
    // 别让它拿着 0 去请求菜单然后报一堆错
    uni.showToast({ title: '先去首页选一家门店', icon: 'none' })
    return
  }

  if (id !== storeId.value) {
    // 换了门店就清空购物车：在 A 店点的菜到了 B 店可能没有、价格也不一样
    clearCart()
    cart.storeId = id
    cart.storeName = storeState.current?.name || ''
    storeId.value = id
    storeName.value = cart.storeName
  }
  loadMenu()

  // 结算弹层开着的时候切出去又切回来（最典型的是点「登录后可用券」去登录），
  // **得重新拉一次券**：登录态和券都是刚变的，不刷的话弹层里还写着
  // 「登录后可用券」——明明已经登录了。这个是跑起来才发现的
  if (cartVisible.value) loadUsableCoupons()
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
  /* 分类栏是横向滚动的，**不能让它们被挤窄**：`.category-row` 是 flex 容器，
     不写这条的话所有分类会一起挤进屏幕宽度，「招牌面食」会折成两行。
     （这行是补的——仓库里那张旧截图就已经折着了，一直没人发现） */
  flex-shrink: 0;
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
  /* 底部留出购物车栏的高度：它是 position: fixed 盖在内容上的，
     不留白的话最后一道菜会被压住点不到（购物车栏 110rpx + 一点余量） */
  padding: 20rpx 24rpx 140rpx;
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
  /* **不能用 bottom: 0**：这一页现在是 tab 页，底部被 tabBar 占着。
     小程序里 tabBar 是原生的、页面视口本来就不含它，`bottom: 0` 没问题；
     但 H5 里 tabBar 是个 DOM 元素，两个都贴底就会压在一起。
     `--window-bottom` 是 uni-app 给的变量：小程序里是 0，H5 里是 tabBar 的高度 */
  bottom: var(--window-bottom);
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
  /* **不能用 bottom: 0**（和下面的 .cart-bar 同一条道理）：
     这一页是 tab 页，H5 里 tabBar 是个 DOM 元素、盖在页面上层，
     弹层贴到屏幕最底下的话，底部那截（勾规格的地方和「加入购物车」按钮）
     会被 tabBar 压住。`--window-bottom` 小程序里是 0、H5 里是 tabBar 的高度，
     弹层从 tabBar 上沿开始，两边都不会压 */
  bottom: var(--window-bottom);
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

.foot-total {
  display: flex;
  flex-direction: column;
}

/* ---------- 用券 ---------- */

/* 登录后才有券——所以这里不是"没有券"，是个入口 */
.coupon-login {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx 32rpx;
  border-top: 1rpx solid #f0f0f0;
  font-size: 26rpx;
  color: #1f1f1f;
}

.coupon-arrow {
  color: #c0c0c0;
  font-size: 30rpx;
}

.coupon-box {
  padding: 20rpx 32rpx 0;
  border-top: 1rpx solid #f0f0f0;
}

.coupon-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12rpx;
}

.coupon-title {
  font-size: 26rpx;
  color: #1f1f1f;
}

.coupon-hint {
  font-size: 24rpx;
  color: #a0a0a0;
}

/* 一行一张券：点一下选它，再点一下取消。
   **不做"不使用优惠券"那一项**——点一下已选中的就是取消，少一个选项少一次犹豫 */
.coupon-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18rpx 24rpx;
  margin-bottom: 12rpx;
  border-radius: 12rpx;
  border: 1rpx solid #eee;
  font-size: 26rpx;
  color: #1f1f1f;
}

.coupon-item.active {
  border-color: #1f1f1f;
  background: #f7f7f7;
}

.coupon-value {
  font-weight: 600;
}

.sheet-total {
  font-size: 32rpx;
  font-weight: 600;
  color: #1f1f1f;
}

/* 用了券才出现：把原价摆在下面，不然"合计怎么少了"要用户自己算 */
.sheet-origin {
  display: block;
  margin-top: 4rpx;
  font-size: 22rpx;
  color: #a0a0a0;
  text-decoration: line-through;
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

/* 「连点可加多份」：比「多选」再淡一点，别抢主信息的注意力 */
.group-hint {
  font-size: 22rpx;
  color: #c0c0c0;
  margin-left: 16rpx;
}

.option-row {
  display: flex;
  flex-wrap: wrap;
}

.option {
  display: flex;
  align-items: center;
  padding: 14rpx 24rpx;
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

/* 加减号：多选组选中后才出现 */
.opt-btn {
  padding: 0 14rpx;
  font-size: 30rpx;
  line-height: 1;
}

.opt-label {
  padding: 0 2rpx;
}

.opt-count {
  margin-left: 8rpx;
  font-size: 24rpx;
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
