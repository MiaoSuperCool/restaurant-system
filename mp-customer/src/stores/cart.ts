/**
 * 购物车
 *
 * 没有用 Pinia——顾客端的跨页状态只有这一个，模块级的 `reactive` 就够了，
 * 少一个依赖。小程序里所有页面在同一个 JS 上下文，模块单例是可靠的
 * （页面之间跳转不会重置模块状态）。
 */
import { computed, reactive } from 'vue'

/** 购物车里的一行。同一道菜选了不同规格算两行——后厨出单要看清 */
export interface CartItem {
  /** 唯一键：dish_id + 排序后的选项 id */
  key: string
  dish_id: number
  name: string
  unit_price: number
  quantity: number
  option_ids: number[]
  options_text: string
}

export const cart = reactive({
  storeId: 0,
  storeName: '',
  items: [] as CartItem[],
  /** 堂食 / 自取 / 外卖 */
  source: 'dine_in',
  remark: '',
})

export const cartTotal = computed(() =>
  cart.items.reduce((sum, item) => sum + item.unit_price * item.quantity, 0)
)

export const cartCount = computed(() =>
  cart.items.reduce((sum, item) => sum + item.quantity, 0)
)

/** 加入购物车：同菜同规格合并数量，不同规格另起一行 */
export function addToCart(picked: Omit<CartItem, 'key'>) {
  const key = `${picked.dish_id}-${[...picked.option_ids].sort().join('_')}`
  const existing = cart.items.find((item) => item.key === key)
  if (existing) {
    existing.quantity += picked.quantity
    return
  }
  cart.items.push({ ...picked, key })
}

export function changeQuantity(item: CartItem, delta: number) {
  const next = item.quantity + delta
  if (next <= 0) {
    removeItem(item)
    return
  }
  item.quantity = next
}

export function removeItem(item: CartItem) {
  const index = cart.items.findIndex((row) => row.key === item.key)
  if (index >= 0) cart.items.splice(index, 1)
}

/**
 * 清空购物车
 *
 * 切门店时也要调一次——在 A 店点了菜再去 B 店，那些菜在 B 店可能没有、
 * 价格也不一样，留着只会出错。
 */
export function clearCart() {
  cart.items = []
  cart.remark = ''
}
