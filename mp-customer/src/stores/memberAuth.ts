/**
 * 顾客登录态：token + 会员档案
 *
 * **这一端不强制登录**：菜单、下单、查订单都不需要登录，一期就是这样，
 * 二期加会员也还是这样——顾客扫了码就能点，注册是「想攒积分/有券要花」时才做的事。
 * 所以这个 store 的作用是「登录过就知道自己是谁」，而不是「没登录什么都干不了」。
 *
 * 没有用 Pinia：和员工端（mp-staff）一样，一个人、一份状态，
 * 模块级的 reactive 够了（多一个依赖换不来什么）。
 */
import { reactive } from 'vue'
import { TOKEN_KEY, getToken } from '@/api/request'
import type { Member } from '@/api/types'

interface MemberState {
  member: Member | null
}

export const memberState = reactive<MemberState>({ member: null })

export function isLoggedIn(): boolean {
  return !!getToken()
}

export function setSession(data: { token?: string; member: Member }) {
  if (data.token) uni.setStorageSync(TOKEN_KEY, data.token)
  memberState.member = data.member
}

export function clearSession() {
  uni.removeStorageSync(TOKEN_KEY)
  memberState.member = null
}

/** 显示名：优先昵称，没有就用手机号后四位（顾客多半没填昵称） */
export function displayName(): string {
  const member = memberState.member
  if (!member) return ''
  if (member.nickname) return member.nickname
  if (member.mobile) return `顾客${member.mobile.slice(-4)}`
  return '顾客'
}