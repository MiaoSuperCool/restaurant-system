<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getMembers } from '@/api/members'
import { createOrder } from '@/api/orders'
import { getStoreOptions } from '@/api/stores'
import { getStoreMenu } from '@/api/storeMenu'
import type { Member, StoreMenuRow, StoreOption } from '@/api/types'
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
  memberPickerVisible.value = false
}

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
      // 不传就是散客单——收款时用不了储值
      member_id: member.value?.id,
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
        </div>

        <div class="cart-foot">
          <div class="total">
            <span>合计</span>
            <span class="total-value">{{ formatPrice(cartTotal) }}</span>
          </div>
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
}

.dish-card:hover {
  border-color: #1f1f1f;
  background: #fafafa;
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
