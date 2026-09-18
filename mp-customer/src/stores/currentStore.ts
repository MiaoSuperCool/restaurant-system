/**
 * 当前门店
 *
 * **为什么要有个「当前门店」**：改成底部四个 tab 之后，「点餐」是个常驻页面，
 * 它得知道自己点的是哪家店的菜。以前是「首页选店 → 跳菜单页」带着 `storeId` 走，
 * 现在没有那一步跳转了，门店得存在一个地方。
 *
 * 存本地存储而不是内存：小程序被切到后台再回来、或者用户从点餐切到订单再切回来，
 * 内存里的模块状态不一定还在，而「我刚才点的是解放路店」这件事不能忘。
 *
 * **扫码进店那条链路还没做**（见 `docs/分期工程.md` 的附录），真做的时候
 * 扫码进来的门店会覆盖这里存的值——所以这里只有 `setCurrentStore` 一个写入口。
 */
import { reactive } from 'vue'
import type { StoreBrief } from '@/api/types'

const STORAGE_KEY = 'mp_customer_store'

export const storeState = reactive<{ current: StoreBrief | null }>({
  current: null,
})

/** 从本地存储读回来。App 启动和每次进页面时调一下就行，重复调没有副作用 */
export function loadCurrentStore() {
  const cached = uni.getStorageSync(STORAGE_KEY)
  if (cached) {
    storeState.current = cached
  }
  return storeState.current
}

export function setCurrentStore(store: StoreBrief) {
  storeState.current = store
  uni.setStorageSync(STORAGE_KEY, store)
}

export function currentStoreId(): number {
  return loadCurrentStore()?.id ?? 0
}