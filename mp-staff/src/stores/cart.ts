/**
 * 代客点单的购物车
 *
 * 单独一个模块而不是塞在页面里：**离开点单页（去看订单、接个电话）再回来，
 * 点了半天的菜不能没**。页面级的状态一 `onUnload` 就没了，
 * 模块级的 reactive 能一直活着。
 *
 * 和后端 `build_order_item` 一个道理：**同一道菜 + 同一组规格才算一行**，
 * 规格不同要分开——后厨出单要看清（「加蛋」和「不加蛋」是两份不同的菜）。
 */
import { computed, reactive } from 'vue'

export interface CartItem {
  /** 同一道菜 + 同一组规格算一行，这就是它的身份 */
  key: string
  dish_id: number
  name: string
  /** 单价（本店价 + 规格加价），由选择器算好传进来 */
  unit_price: number
  quantity: number
  option_ids: number[]
  /** 规格的中文说明（「大份 / 特辣 / 加蛋」），显示用 */
  options_text: string
}

export const cartState = reactive({ items: [] as CartItem[] })

export const cartCount = computed(() =>
  cartState.items.reduce((sum, item) => sum + item.quantity, 0)
)

/** 原价合计。**只是给收银员报价用的**，真正的钱由后端下单时算 */
export const cartTotal = computed(() =>
  cartState.items.reduce((sum, item) => sum + item.unit_price * item.quantity, 0)
)

export function addToCart(picked: Omit<CartItem, 'key'>) {
  const key = `${picked.dish_id}-${[...picked.option_ids].sort().join('_')}`
  const existing = cartState.items.find((item) => item.key === key)
  if (existing) {
    existing.quantity += picked.quantity
    return
  }
  cartState.items.push({ ...picked, key })
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
  cartState.items = cartState.items.filter((row) => row.key !== item.key)
}

export function clearCart() {
  cartState.items = []
}