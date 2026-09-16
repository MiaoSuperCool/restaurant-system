<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getMembers } from '@/api/members'
import { getUsableCoupons } from '@/api/coupons'
import { createOrder } from '@/api/orders'
import { getStoreOptions } from '@/api/stores'
import { getStoreMenu } from '@/api/storeMenu'
import type { Member, StoreMenuRow, StoreOption, UserCoupon } from '@/api/types'
import DishOptionPicker from '@/components/DishOptionPicker.vue'
import type { PickedDish } from '@/components/DishOptionPicker.vue'
import { ORDER_SOURCE_OPTIONS } from '@/constants/order'
import { useAuthStore } from '@/stores/auth'
import { formatPrice } from '@/utils/format'

const authStore = useAuthStore()
const router = useRouter()

/** 购物车里的一行：同一道菜选了不同规格算两行 */
interface CartItem {
  key: string
  dish_id: number
  name: string
  unit_price: number
  quantity: number
  option_ids: number[]
  options_text: string
}

const storeOptions = ref<StoreOption[]>([])
const storeId = ref<number | null>(authStore.staff?.store_id ?? null)
const canPickStore = computed(() => authStore.hasPermission('store:view'))

const dishes = ref<StoreMenuRow[]>([])
const activeCategory = ref<number | null>(null)
const search = ref('')
const loading = ref(false)
const submitting = ref(false)

const pickerVisible = ref(false)
const pickingDish = ref<StoreMenuRow | null>(null)

const cart = ref<CartItem[]>([])
const source = ref('dine_in')
const remark = ref('')

// ---------- 关联会员 ----------
// 收银台那一幕：顾客报手机号 → 搜出来 → 挂到单上。挂了才能用储值付账，
// 散客单扣不了任何人的余额
const member = ref<Member | null>(null)
const memberPickerVisible = ref(false)
const memberSearch = ref('')
const memberResults = ref<Member[]>([])
const memberLoading = ref(false)

function openMemberPicker() {
  memberSearch.value = ''
  memberResults.value = []
  memberPickerVisible.value = true
}

async function searchMembers() {
  memberLoading.value = true
  try {
    const data = await getMembers({ search: memberSearch.value.trim() })
    memberResults.value = data.members
  } catch {
    memberResults.value = []
  } finally {
    memberLoading.value = false
  }
}

function pickMember(row: Member) {
  member.value = row
  pointsToUse.value = 0
  memberPickerVisible.value = false
}

// 用多少积分抵扣。默认 0（不抵）——收银员不问就不动它
const pointsToUse = ref(0)

/**
 * 这些分能抵多少钱（**只是提示**，真正的数由后端下单时算）
 *
 * 用后端给的「全部积分抵多少」按比例折算，而不是在这儿写一遍「100 分抵 1 元」——
 * 比例只该存在于后端，将来改了这里自动跟上。有舍入差也没关系：
 * 收银员拿它报价，最后以订单上的实付为准。
 */
const pointsDiscount = computed(() => {
  const points = member.value?.points
  if (!points?.balance || !points.amount || pointsToUse.value <= 0) return 0
  const ratio = pointsToUse.value / points.balance
  return Math.round(points.amount * ratio * 100) / 100
})

/** 分类从菜品里现推，避免多一次请求；只展示真的上了菜的分类 */
const categories = computed(() => {
  const seen = new Map<number, string>()
  for (const dish of dishes.value) {
    if (!seen.has(dish.category_id)) seen.set(dish.category_id, dish.category_name ?? '未分类')
  }
  return [...seen.entries()].map(([id, name]) => ({ id, name }))
})

const visibleDishes = computed(() => {
  const keyword = search.value.trim()
  return dishes.value.filter((dish) => {
    if (activeCategory.value !== null && dish.category_id !== activeCategory.value) return false
    if (keyword && !dish.name.includes(keyword)) return false
    return true
  })
})

const cartTotal = computed(
  () => cart.value.reduce((sum, item) => sum + item.unit_price * item.quantity, 0)
)
const cartCount = computed(() => cart.value.reduce((sum, item) => sum + item.quantity, 0))

// ---------- 用券 ----------
// 放在购物车合计后面，是因为「哪些券能用」得看金额（门槛按商品原价算）
//
// 看券和看余额是同一个权限的活，后端也是这两个码任一
const canSeeCoupons = computed(
  () => authStore.hasPermission('member:balance:view') || authStore.hasPermission('coupon:verify')
)

const couponId = ref<number | null>(null)
const usableCoupons = ref<UserCoupon[]>([])

/**
 * 问后端「这一单能用哪些券」
 *
 * **能不能用只能后端说了算**——过没过期、这家店能不能用、够不够门槛，
 * 三条都得看。前端不自己筛，「筛漏一张」比「多问一次接口」糟得多。
 *
 * 金额一变就重问：门槛看的是商品原价，减掉一道菜之后原来那张券可能就
 * 够不上了，不该还挂在下拉框里等着下单时报错。
 */
async function loadUsableCoupons() {
  if (!member.value || storeId.value === null || cartTotal.value <= 0) {
    usableCoupons.value = []
    couponId.value = null
    return
  }
  try {
    const data = await getUsableCoupons(member.value.id, {
      store_id: storeId.value,
      amount: cartTotal.value,
    })
    usableCoupons.value = data.coupons
    if (couponId.value !== null && !data.coupons.some((coupon) => coupon.id === couponId.value)) {
      couponId.value = null
    }
  } catch {
    // 拦截器已提示
    usableCoupons.value = []
  }
}

watch([() => member.value?.id, storeId, cartTotal], loadUsableCoupons)

/** 选中的券能抵多少——**后端按当前金额算好给的**，不是前端拿面额自己算的 */
const couponDiscount = computed(
  () => usableCoupons.value.find((coupon) => coupon.id === couponId.value)?.discount ?? 0
)

/**
 * 预计实付（**只是提示**，真正的数由后端下单时算）
 *
 * 券和积分是**各自独立**的：两边的基数都是商品原价，不是「扣完券再扣积分」。
 * 所以这里是各减各的，不是连乘。
 */
const expectedPayable = computed(() =>
  Math.max(cartTotal.value - couponDiscount.value - pointsDiscount.value, 0)
)

async function loadStores() {
  if (!canPickStore.value) return
  try {
    const data = await getStoreOptions()
    storeOptions.value = data.stores
    if (storeId.value === null && data.stores.length > 0) {
      storeId.value = data.stores[0].id
    }
  } catch {
    // 拦截器已提示
  }
}

async function loadMenu() {
  if (storeId.value === null) return
  loading.value = true
  try {
    const data = await getStoreMenu(storeId.value)
    // 本店下架的菜不显示——收银台上摆着点不了的菜只会添乱
    dishes.value = data.dishes.filter((dish) => dish.is_available)
    activeCategory.value = null
    cart.value = []
  } catch {
    dishes.value = []
  } finally {
    loading.value = false
  }
}

function pickDish(dish: StoreMenuRow) {
  // 没有规格的菜直接进购物车，少一次弹窗
  if (dish.option_groups.length === 0) {
    addToCart({
      dish_id: dish.dish_id, name: dish.name, unit_price: dish.price,
      quantity: 1, option_ids: [], options_text: '',
    })
    return
  }
  pickingDish.value = dish
  pickerVisible.value = true
}

function addToCart(picked: PickedDish) {
  // 同一道菜 + 同一组规格才算同一行；规格不同要分开——后厨出单要看清
  const key = `${picked.dish_id}-${[...picked.option_ids].sort().join('_')}`
  const existing = cart.value.find((item) => item.key === key)
  if (existing) {
    existing.quantity += picked.quantity
  } else {
    cart.value.push({ ...picked, key })
  }
}

function changeQuantity(item: CartItem, delta: number) {
  const next = item.quantity + delta
  if (next <= 0) {
    removeItem(item)
    return
  }
  item.quantity = next
}

function removeItem(item: CartItem) {
  cart.value = cart.value.filter((row) => row.key !== item.key)
}

function clearCart() {
  cart.value = []
}

async function handleSubmit() {
  if (storeId.value === null) {
    ElMessage.warning('请先选择门店')
    return
  }
  if (cart.value.length === 0) {
    ElMessage.warning('还没点菜')
    return
  }

  submitting.value = true
  try {
    // 只传菜品和数量，不传价格——后端会按本店实际价重算一遍
    const order = await createOrder({
      store_id: storeId.value,
      // 不传就是散客单——收款时用不了储值、也用不了积分、更用不了券
      member_id: member.value?.id,
      coupon_id: couponId.value ?? undefined,
      points_to_use: pointsToUse.value || 0,
      source: source.value,
      remark: remark.value.trim(),
      items: cart.value.map((item) => ({
        dish_id: item.dish_id,
        quantity: item.quantity,
        option_ids: item.option_ids,
      })),
    })
    ElMessage.success(`下单成功，单号 ${order.order_no}`)
    cart.value = []
    remark.value = ''
    member.value = null
    couponId.value = null
    usableCoupons.value = []
    router.push('/orders')
  } catch {
    // 拦截器已提示（必选规格没选、本店已下架等后端也会再校验一遍）
  } finally {
    submitting.value = false
  }
}

/** 清空购物车前确认一下——点错一下把一单菜清了很气人 */
async function handleClearCart() {
  if (cart.value.length === 0) return
  try {
    await ElMessageBox.confirm('购物车里还有没提交的菜，确定要清空吗？', '清空点单', {
      type: 'warning', confirmButtonText: '清空', cancelButtonText: '继续点',
    })
  } catch {
    return
  }
  clearCart()
}

/**
 * 菜品照片通过 CSS 变量传给卡片的伪元素
 *
 * **为什么绕一层变量**：`filter: blur()` 作用于整个元素——直接给 `.dish-card`
 * 加背景图再 blur 的话，卡片上的文字也会被糊掉。所以背景得是单独一层
 * （`::before`），而伪元素拿不到 Vue 的绑定，只能用变量传进去。
 *
 * 没图就返回 undefined，卡片走原来的样子。
 */
function dishPhotoVars(dish: StoreMenuRow): Record<string, string> | undefined {
  if (!dish.image) return undefined
  return { '--dish-photo': `url(${dish.image})` }
}

onMounted(async () => {
  await loadStores()
  loadMenu()
})
</script>

<template>
  <div class="new-order">
    <div class="toolbar">
      <el-select
        v-if="canPickStore"
        v-model="storeId"
        placeholder="选择门店"
        class="store-select"
        @change="loadMenu"
      >
        <el-option
          v-for="store in storeOptions"
          :key="store.id"
          :label="`${store.name}（${store.code}）`"
          :value="store.id"
        />
      </el-select>
      <span v-else class="store-name">{{ authStore.staff?.store_name }}</span>

      <el-input
        v-model="search"
        placeholder="搜索菜品"
        clearable
        class="search-input"
      />
      <el-button @click="loadMenu">刷新菜单</el-button>
    </div>

    <p v-if="storeId === null" class="empty-hint">
      你的账号没有归属门店，也没看到门店的权限，无法点单。
    </p>

    <div v-else class="body">
      <!-- 左：菜单 -->
      <div class="menu-pane">
        <div class="category-bar">
          <span
            class="category"
            :class="{ active: activeCategory === null }"
            @click="activeCategory = null"
          >
            全部
          </span>
          <span
            v-for="category in categories"
            :key="category.id"
            class="category"
            :class="{ active: activeCategory === category.id }"
            @click="activeCategory = category.id"
          >
            {{ category.name }}
          </span>
        </div>

        <div v-loading="loading" class="dish-grid">
          <div
            v-for="dish in visibleDishes"
            :key="dish.dish_id"
            class="dish-card"
            :class="{ 'has-photo': !!dish.image }"
            :style="dishPhotoVars(dish)"
            @click="pickDish(dish)"
          >
            <div class="dish-name">{{ dish.name }}</div>
            <div class="dish-desc">{{ dish.description || ' ' }}</div>
            <div class="dish-bottom">
              <span class="dish-price">{{ formatPrice(dish.price) }}</span>
              <span v-if="dish.option_groups.length" class="dish-tag">可选规格</span>
              <span v-if="dish.has_price_override" class="dish-tag store-price">本店价</span>
            </div>
          </div>
          <p v-if="!loading && visibleDishes.length === 0" class="empty-hint">
            这个分类下暂时没有可点的菜
          </p>
        </div>
      </div>

      <!-- 右：购物车 -->
      <aside class="cart-pane">
        <div class="cart-head">
          <span>已点 {{ cartCount }} 份</span>
          <el-button v-if="cart.length" link @click="handleClearCart">清空</el-button>
        </div>

        <div class="cart-list">
          <div v-for="item in cart" :key="item.key" class="cart-item">
            <div class="cart-line">
              <span class="cart-name">
                {{ item.name }}
                <span v-if="item.options_text" class="cart-options">{{ item.options_text }}</span>
              </span>
              <el-button link class="cart-remove" @click="removeItem(item)">×</el-button>
            </div>
            <div class="cart-line">
              <span class="cart-price">{{ formatPrice(item.unit_price) }}</span>
              <span class="qty">
                <el-button link @click="changeQuantity(item, -1)">−</el-button>
                <span class="qty-value">{{ item.quantity }}</span>
                <el-button link @click="changeQuantity(item, 1)">＋</el-button>
              </span>
              <span class="cart-subtotal">{{ formatPrice(item.unit_price * item.quantity) }}</span>
            </div>
          </div>
          <p v-if="cart.length === 0" class="empty-hint">点左边的菜加进来</p>
        </div>

        <div class="cart-form">
          <el-select v-model="source" class="full-width">
            <el-option
              v-for="item in ORDER_SOURCE_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
          <el-input v-model="remark" placeholder="备注（少辣、不要香菜…）" class="full-width" />

          <!-- 关联会员：挂了才能用储值付账 -->
          <div class="member-row">
            <template v-if="member">
              <span class="member-name">
                会员 {{ member.nickname || member.mobile }}
                <span v-if="member.balance" class="member-balance">
                  余额 {{ formatPrice(member.balance.total) }}
                </span>
              </span>
              <el-button link class="member-clear" @click="member = null">×</el-button>
            </template>
            <el-button v-else link class="member-pick" @click="openMemberPicker">
              + 关联会员（用储值付账要先挂上）
            </el-button>
          </div>

          <!-- 积分抵扣：挂了会员才显示。用多少分由收银员填，后端会按订单金额截断 -->
          <div v-if="member?.points" class="points-row">
            <span class="member-name">
              可用积分 {{ member.points.balance }} 分
              <span v-if="member.points.amount" class="member-balance">
                （抵 {{ formatPrice(member.points.amount) }}）
              </span>
            </span>
            <el-input-number
              v-model="pointsToUse"
              :min="0"
              :max="member.points.balance"
              :precision="0"
              :controls="false"
              :disabled="member.points.balance === 0"
              placeholder="用多少分"
              class="points-input"
            />
          </div>

          <!-- 用券：挂了会员才显示。下拉里只放**这单真能用**的券 -->
          <div v-if="member && canSeeCoupons" class="points-row">
            <span class="member-name">
              优惠券
              <span v-if="usableCoupons.length === 0" class="member-balance">没有能用的</span>
            </span>
            <el-select
              v-if="usableCoupons.length"
              v-model="couponId"
              clearable
              placeholder="不用券"
              class="coupon-select"
            >
              <el-option
                v-for="coupon in usableCoupons"
                :key="coupon.id"
                :label="`${coupon.template_name}（抵 ${formatPrice(coupon.discount ?? 0)}）`"
                :value="coupon.id"
              />
            </el-select>
          </div>
        </div>

        <div class="cart-foot">
          <div class="total">
            <span>合计</span>
            <span class="total-value">{{ formatPrice(cartTotal) }}</span>
          </div>
          <!-- 只是提示：真正的实付由后端下单时算，提交后到订单页看确切的数 -->
          <p v-if="couponDiscount > 0 || pointsDiscount > 0" class="discount-line">
            <span v-if="couponDiscount > 0">券抵 −{{ formatPrice(couponDiscount) }}</span>
            <span v-if="couponDiscount > 0 && pointsDiscount > 0"> · </span>
            <span v-if="pointsDiscount > 0">积分抵 −{{ formatPrice(pointsDiscount) }}</span>
            · 预计实付 {{ formatPrice(expectedPayable) }}
          </p>
          <el-button
            type="primary"
            class="submit-btn"
            :loading="submitting"
            :disabled="cart.length === 0"
            @click="handleSubmit"
          >
            提交订单
          </el-button>
          <p class="foot-hint">下单后到「订单」页接单、收款</p>
        </div>
      </aside>
    </div>

    <DishOptionPicker
      v-model="pickerVisible"
      :dish="pickingDish"
      @confirm="addToCart"
    />

    <!-- 选会员：顾客报手机号，搜出来点一行 -->
    <el-dialog v-model="memberPickerVisible" title="关联会员" width="460px">
      <div class="member-search">
        <el-input
          v-model="memberSearch"
          placeholder="顾客报的手机号，或昵称"
          clearable
          @keyup.enter="searchMembers"
          @clear="searchMembers"
        />
        <el-button @click="searchMembers">搜索</el-button>
      </div>
      <el-table
        v-loading="memberLoading"
        :data="memberResults"
        size="small"
        height="260"
        @row-click="pickMember"
      >
        <el-table-column prop="nickname" label="昵称" width="110" />
        <el-table-column prop="mobile" label="手机号" width="130" />
        <el-table-column label="余额" min-width="90">
          <template #default="{ row }">
            {{ row.balance ? formatPrice(row.balance.total) : '—' }}
          </template>
        </el-table-column>
      </el-table>
      <p class="member-hint">
        点一行就选它。搜不到就先去「会员」页建档——散客单也能下单，只是用不了储值。
      </p>
    </el-dialog>
  </div>
</template>

<style scoped>
.new-order {
  padding: 24px 32px;
  height: 100vh;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
}

.store-select {
  width: 220px;
}

.store-name {
  font-size: 15px;
  font-weight: 600;
  color: #1f1f1f;
}

.search-input {
  width: 200px;
}

.body {
  flex: 1;
  display: flex;
  gap: 20px;
  min-height: 0;
}

/* ---------- 左：菜单 ---------- */
.menu-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.category-bar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.category {
  padding: 6px 14px;
  border-radius: 16px;
  font-size: 13px;
  color: #1f1f1f;
  background: #f2f2f2;
  cursor: pointer;
  transition: background 0.15s;
}

.category:hover {
  background: #e8e8e8;
}

.category.active {
  background: #1f1f1f;
  color: #fff;
}

.dish-grid {
  flex: 1;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
  align-content: start;
}

.dish-card {
  border: 1px solid #e5e5e5;
  border-radius: 10px;
  padding: 14px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  display: flex;
  flex-direction: column;
  min-height: 104px;
  /* 背景图那层要裁在圆角里 */
  position: relative;
  overflow: hidden;
}

.dish-card:hover {
  border-color: #1f1f1f;
  background: #fafafa;
}

/* 菜品照片作背景：模糊 + 压淡，让它当氛围而不是抢戏
 *
 * 单独一层伪元素是必须的——`filter: blur()` 作用于**整个元素**，直接加在
 * `.dish-card` 上的话，菜名和价格也会被糊掉。
 * `inset: -8px` 往外扩一圈：blur 会让边缘透出底色，扩出去就看不到了。
 * 图片地址由 Vue 通过 `--dish-photo` 传进来（伪元素拿不到绑定）。
 */
.dish-card.has-photo::before {
  content: '';
  position: absolute;
  inset: -8px;
  background-image: var(--dish-photo);
  background-size: cover;
  background-position: center;
  /* 模糊要留着（是「氛围」不是「照片」），但别糊到看不出是什么菜——
     blur 越小越能认出形状，靠 opacity 压住彩度 */
  filter: blur(3px) saturate(0.9);
  opacity: 0.45;
  z-index: 0;
}

/* 卡片内容压在背景那层上面 */
.dish-card.has-photo > * {
  position: relative;
  z-index: 1;
}

.dish-name {
  font-size: 15px;
  font-weight: 600;
  color: #1f1f1f;
}

.dish-desc {
  font-size: 12px;
  color: #a0a0a0;
  margin-top: 4px;
  flex: 1;
  overflow: hidden;
}

.dish-bottom {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
}

.dish-price {
  font-size: 16px;
  font-weight: 600;
  color: #1f1f1f;
}

.dish-tag {
  font-size: 11px;
  color: #8a8a8a;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  padding: 0 4px;
}

.dish-tag.store-price {
  color: #c45656;
  border-color: #f0d0d0;
}

/* ---------- 右：购物车 ---------- */
.cart-pane {
  width: 330px;
  flex-shrink: 0;
  border: 1px solid #e5e5e5;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  padding: 16px;
  background: #fafafa;
}

.cart-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  font-weight: 600;
  color: #1f1f1f;
  padding-bottom: 12px;
  border-bottom: 1px solid #e5e5e5;
}

.cart-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px 0;
}

.cart-item {
  padding: 8px 0;
  border-bottom: 1px dashed #e8e8e8;
}

.cart-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.cart-name {
  font-size: 13px;
  color: #1f1f1f;
}

.cart-options {
  font-size: 12px;
  color: #8a8a8a;
  margin-left: 4px;
}

.cart-remove {
  color: #a0a0a0;
}

.cart-price {
  font-size: 12px;
  color: #8a8a8a;
}

.qty {
  display: flex;
  align-items: center;
  gap: 2px;
}

.qty-value {
  font-size: 13px;
  min-width: 20px;
  text-align: center;
}

.cart-subtotal {
  font-size: 13px;
  font-weight: 600;
  color: #1f1f1f;
}

.cart-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 0;
  border-top: 1px solid #e5e5e5;
}

.member-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 24px;
}

.member-name {
  font-size: 13px;
  color: #1f1f1f;
}

.member-balance {
  margin-left: 8px;
  color: #8a8a8a;
}

.member-clear {
  color: #a0a0a0;
}

.member-pick {
  font-size: 13px;
  color: #8a8a8a;
}

.member-search {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.member-hint {
  margin-top: 12px;
  font-size: 12px;
  color: #a0a0a0;
}

.points-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 24px;
}

.points-input {
  width: 110px;
}

/* 券名比「用多少分」长得多（「解放路店周年庆 满 50 减 15（抵 ¥15.00）」），
   让它把「优惠券」三个字右边剩下的宽度都吃掉，而不是截成「（抵 ¥20...」 */
.coupon-select {
  flex: 1;
  min-width: 0;
}

.discount-line {
  font-size: 12px;
  color: #c45656;
  margin-top: 4px;
}

.full-width {
  width: 100%;
}

.cart-foot {
  border-top: 1px solid #e5e5e5;
  padding-top: 12px;
}

.total {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 13px;
  color: #666;
  margin-bottom: 10px;
}

.total-value {
  font-size: 22px;
  font-weight: 600;
  color: #1f1f1f;
}

.submit-btn {
  width: 100%;
  height: 40px;
}

.foot-hint {
  font-size: 12px;
  color: #a0a0a0;
  text-align: center;
  margin-top: 8px;
}

.empty-hint {
  font-size: 13px;
  color: #a0a0a0;
  text-align: center;
  padding: 24px 0;
}
</style>
