import { request } from './request'
import type {
  ClaimableCoupon,
  Member,
  MemberCoupon,
  Pagination,
  UsableCoupon,
} from './types'

/** 登录返回的 data */
export interface MemberLoginResult {
  token: string
  expires_in: number
  /** 这个手机号是不是刚建的档——前端拿它决定要不要说一句「欢迎加入」 */
  is_new: boolean
  member: Member
}

/** 储值余额（对应 balance.py 的 Balance.to_dict） */
export interface MemberBalance {
  member_id: number
  principal: number
  bonus: number
  total: number
}

/** 积分（对应 points.py 的 Points.to_dict） */
export interface MemberPoints {
  member_id: number
  balance: number
  /** 这些分能抵多少钱——后端算好的，前端别自己乘除 */
  amount: number
}

/** 我的账户：档案 + 余额 + 积分 */
export interface MyAccount extends Member {
  balance: MemberBalance
  points: MemberPoints
}

/**
 * 发验证码
 *
 * **演示环境会把验证码放在 `code` 字段里直接返回**（真实环境发短信，
 * 那个字段不会有）。所以登录页可以拿它自动填上，省得去翻后端日志。
 */
export function sendCode(mobile: string) {
  return request<{ mobile: string; expires_in: number; code?: string; note?: string }>({
    url: '/api/public/auth/code',
    method: 'POST',
    data: { mobile },
  })
}

/**
 * 验证码换 token——**登录即注册**
 *
 * 手机号在店里没建过档的话，这一步顺手建一个，不单独做注册页。
 */
export function loginWithCode(mobile: string, code: string) {
  return request<MemberLoginResult>({
    url: '/api/public/auth/token',
    method: 'POST',
    data: { mobile, code },
  })
}

/** 我的账户（要登录） */
export function getMyAccount() {
  return request<MyAccount>({ url: '/api/public/me', method: 'GET' })
}

/** 我的券包（要登录） */
export function getMyCoupons(params: { status?: string; page?: number } = {}) {
  return request<{ coupons: MemberCoupon[]; pagination: Pagination }>({
    url: '/api/public/me/coupons',
    method: 'GET',
    params,
  })
}

/**
 * 券中心：有哪些券能领，以及我各领了几张
 *
 * **不能领的也会返回**（带 `blocked_reason`）——一张券摆在眼前却说不出
 * 为什么领不了，比它干脆不出现更让人恼火。
 */
export function getCouponCenter() {
  return request<{ coupons: ClaimableCoupon[] }>({
    url: '/api/public/coupons',
    method: 'GET',
  })
}

/** 领一张券（要登录） */
export function claimCoupon(templateId: number) {
  return request<MemberCoupon>({
    url: `/api/public/coupons/${templateId}/claim`,
    method: 'POST',
  })
}
/**
 * 结算时「这一单能用哪些券」（要登录）
 *
 * 要传门店和金额——四个条件里有两个（适用门店、满多少）得靠它们判。
 * **用不了的券不会出现在结果里**，返回的每一张都是真能用的；
 * `discount` 也是后端算好的，前端拿它直接显示「能减 X 元」。
 */
export function getUsableCoupons(storeId: number, amount: number) {
  return request<{ coupons: UsableCoupon[] }>({
    url: '/api/public/me/coupons/usable',
    method: 'GET',
    params: { store_id: storeId, amount },
  })
}
